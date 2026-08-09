from flask import Blueprint, jsonify, current_app, request
from datetime import date, timedelta
import os
from db import fetch_all, fetch_one

import math

def to_number(v):
    if v is None: return 0.0
    try:
        f = float(v)
        if math.isnan(f): return 0.0
        return f
    except Exception:
        return 0.0

def fecha_solo(f):
    if not f:
        return ""
    return str(f)[:10]

def primer_dia_mes_menos(fecha, n):
    """Primer día del mes que está `n` meses antes del mes de `fecha`."""
    total = fecha.year * 12 + (fecha.month - 1) - n
    anio, mes = divmod(total, 12)
    return date(anio, mes + 1, 1)

dashboard_bp = Blueprint("dashboard", __name__)

# Caché en memoria de meses cerrados de historial_mensual, por sucursal (clave: "global" o sucursal_id).
# Un mes cerrado ya no cambia, pero se refresca una vez por día por seguridad (p.ej. cambio de mes).
_historial_mensual_cache = {}

@dashboard_bp.route("/api/tiendas", methods=["GET"])
def get_tiendas():
    try:
        sql_tiendas = "SELECT nombre_tienda as nombre, sucursal_id FROM tiendas_acceso"
        tiendas = fetch_all(sql_tiendas)
        return jsonify(tiendas), 200
    except Exception as e:
        current_app.logger.exception("Excepción en get_tiendas: %s", e)
        return jsonify({"error": "Error interno al obtener tiendas"}), 500

@dashboard_bp.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    try:
        # 0. Obtener parámetros de filtro
        s_id_filter = request.args.get("sucursal_id")
        is_global = not s_id_filter or s_id_filter == "global"

        # 1. Nombre de la sucursal
        nombre_sucursal = "Global"
        if not is_global:
            sql_tienda_actual = "SELECT nombre_tienda FROM tiendas_acceso WHERE sucursal_id = :s_id LIMIT 1"
            tienda_actual = fetch_one(sql_tienda_actual, {"s_id": s_id_filter})
            if tienda_actual:
                nombre_sucursal = tienda_actual["nombre_tienda"]

        # --- CÁLCULOS DEL MES ACTUAL ---
        hoy = date.today()
        inicio_mes = hoy.replace(day=1).isoformat()
        
        where_mes = f"WHERE fecha >= :inicio_mes" + (" AND sucursal_id = :s_id" if not is_global else "")
        params_mes = {"inicio_mes": inicio_mes}
        if not is_global:
            params_mes["s_id"] = s_id_filter

        # Ventas del mes (incluye conteo de pedidos para saber si el mes actual tiene datos)
        sql_ventas_mes = f"SELECT SUM(total_pedido) as total, SUM(costo_total) as cogs, COUNT(*) as cnt FROM pedidos {where_mes}"
        res_ventas_mes = fetch_one(sql_ventas_mes, params_mes)
        ventas_mes = to_number(res_ventas_mes.get("total", 0))
        cogs_mes = to_number(res_ventas_mes.get("cogs", 0))
        cnt_pedidos_mes = int(to_number(res_ventas_mes.get("cnt", 0)))

        # Métricas de movimientos_caja del mes (consolidadas en una sola consulta)
        sql_caja_metricas = f"""
            SELECT
                COALESCE(SUM(CASE WHEN tipo = 'salida' AND categoria = 'operativo' AND metodo_pago != 'fondos' THEN monto ELSE 0 END), 0) as gastos_operativos,
                COALESCE(SUM(CASE WHEN tipo = 'salida' AND categoria = 'inventario' AND metodo_pago != 'fondos' THEN monto ELSE 0 END), 0) as compras_inventario,
                COALESCE(SUM(CASE WHEN tipo = 'salida' AND categoria = 'inversion' AND metodo_pago != 'fondos' THEN monto ELSE 0 END), 0) as inversiones_mes,
                COALESCE(SUM(CASE WHEN tipo = 'entrada' AND categoria = 'inversion' THEN monto ELSE 0 END), 0) as inyecciones_mes,
                COALESCE(SUM(CASE WHEN tipo = 'salida' AND metodo_pago = 'fondos' THEN monto ELSE 0 END), 0) as gastos_fondos_mes,
                COALESCE(SUM(CASE WHEN metodo_pago != 'fondos' THEN (CASE WHEN tipo = 'entrada' THEN monto ELSE -monto END) ELSE 0 END), 0) as saldo_caja_mes
            FROM movimientos_caja
            {where_mes}
        """
        res_caja_metricas = fetch_one(sql_caja_metricas, params_mes)
        gastos_operativos = to_number(res_caja_metricas.get("gastos_operativos", 0))
        compras_inventario = to_number(res_caja_metricas.get("compras_inventario", 0))
        inversiones_mes = to_number(res_caja_metricas.get("inversiones_mes", 0))
        inyecciones_mes = to_number(res_caja_metricas.get("inyecciones_mes", 0))
        gastos_fondos_mes = to_number(res_caja_metricas.get("gastos_fondos_mes", 0))
        saldo_caja_mes = to_number(res_caja_metricas.get("saldo_caja_mes", 0))

        # Mermas del mes (estas no son movimientos de caja físicos, son pérdida de valor de inventario)
        sql_merma_mes = f"""
            SELECT COALESCE(SUM(m.cantidad * i.costo_unidad), 0) as total
            FROM mermas m
            JOIN insumos i ON m.insumo_id = i.id
            {where_mes.replace('fecha', 'm.fecha').replace('sucursal_id', 'm.sucursal_id')}
        """
        res_merma_mes = fetch_one(sql_merma_mes, params_mes)
        mermas_mes = to_number(res_merma_mes.get("total", 0))

        # --- LOGICA FINANCIERA DEL MES (Ya existente) ---
        ganancia_neta_mes = ventas_mes - cogs_mes - gastos_operativos - mermas_mes

        # Flujo y gastos del MES desglosados por método de pago (consolidados en una sola consulta)
        sql_por_metodo = f"""
            SELECT
                metodo_pago,
                SUM(CASE WHEN tipo = 'entrada' THEN monto ELSE -monto END) as saldo,
                SUM(CASE WHEN tipo = 'salida' THEN monto ELSE 0 END) as total_gasto,
                COUNT(CASE WHEN tipo = 'salida' THEN 1 END) as num_salidas
            FROM movimientos_caja
            {where_mes}
            GROUP BY metodo_pago
        """
        res_por_metodo = fetch_all(sql_por_metodo, params_mes)
        flujo_por_metodo = {r["metodo_pago"]: round(to_number(r.get("saldo", 0)), 2) for r in res_por_metodo if r.get("metodo_pago")}
        gastos_por_metodo = {r["metodo_pago"]: round(to_number(r.get("total_gasto", 0)), 2) for r in res_por_metodo if r.get("metodo_pago") and to_number(r.get("num_salidas", 0)) > 0}

        # --- HISTORIAL MENSUAL (mes actual en vivo + meses cerrados desde caché diaria) ---
        mes_actual_str = hoy.strftime("%Y-%m")

        # Cantidad de meses de historial a devolver (incluye el mes actual). Configurable vía
        # query param para no forzar siempre 12 meses; por defecto 3 si el cliente no lo envía.
        meses_param_raw = request.args.get("meses_historial") or request.args.get("meses")
        try:
            meses_historial = int(meses_param_raw) if meses_param_raw is not None else 3
        except (TypeError, ValueError):
            meses_historial = 3
        meses_historial = min(max(meses_historial, 1), 24)
        meses_cerrados_necesarios = meses_historial - 1

        sucursal_cache_key = f"{'global' if is_global else s_id_filter}:{meses_historial}"
        hoy_str = hoy.isoformat()

        cache_entry = _historial_mensual_cache.get(sucursal_cache_key)
        if cache_entry and cache_entry["fecha"] == hoy_str:
            meses_cerrados = cache_entry["meses"]
        elif meses_cerrados_necesarios <= 0:
            meses_cerrados = []
            _historial_mensual_cache[sucursal_cache_key] = {"fecha": hoy_str, "meses": meses_cerrados}
        else:
            inicio_rango_historial = primer_dia_mes_menos(hoy, meses_cerrados_necesarios).isoformat()
            where_cerrados = "WHERE fecha < :inicio_mes AND fecha >= :inicio_rango" + (" AND sucursal_id = :s_id" if not is_global else "")
            params_cerrados = {"inicio_mes": inicio_mes, "inicio_rango": inicio_rango_historial, "limite": meses_cerrados_necesarios}
            if not is_global:
                params_cerrados["s_id"] = s_id_filter

            sql_meses_cerrados = f"""
                SELECT
                    TO_CHAR(fecha, 'YYYY-MM') as mes,
                    SUM(total_pedido) as total_ventas
                FROM pedidos
                {where_cerrados}
                GROUP BY mes
                ORDER BY mes DESC
                LIMIT :limite
            """
            meses_cerrados = [
                {**h, "total_ventas": to_number(h["total_ventas"])}
                for h in fetch_all(sql_meses_cerrados, params_cerrados)
            ]
            _historial_mensual_cache[sucursal_cache_key] = {"fecha": hoy_str, "meses": meses_cerrados}

        # El mes en curso solo se incluye si tiene pedidos (igual que el GROUP BY original, que
        # omite meses sin filas), y su total se reutiliza de la consulta de ventas del mes ya hecha arriba.
        historial_mensual = meses_cerrados if cnt_pedidos_mes == 0 else (
            [{"mes": mes_actual_str, "total_ventas": ventas_mes}] + meses_cerrados
        )

        # --- HISTORIAL DIARIO (últimos 15 días) ---
        inicio_15_dias = (hoy - timedelta(days=15)).isoformat()
        where_15_dias = "WHERE fecha >= :inicio_15_dias" + (" AND sucursal_id = :s_id" if not is_global else "")
        params_15_dias = {"inicio_15_dias": inicio_15_dias}
        if not is_global:
            params_15_dias["s_id"] = s_id_filter

        sql_historial_diario = f"""
            SELECT
                TO_CHAR(fecha, 'YYYY-MM-DD') as dia,
                SUM(total_pedido) as total_ventas
            FROM pedidos
            {where_15_dias}
            GROUP BY dia
            ORDER BY dia DESC
            LIMIT 15
        """
        historial_diario = [
            {**d, "total_ventas": to_number(d["total_ventas"])}
            for d in fetch_all(sql_historial_diario, params_15_dias)
        ]

        return jsonify({
            "nombre_sucursal": nombre_sucursal,
            "mes_actual": {
                "ventas": round(ventas_mes, 2),
                "cogs": round(cogs_mes, 2),
                "gastos_operativos": round(gastos_operativos, 2),
                "compras_inventario": round(compras_inventario, 2),
                "inversiones": round(inversiones_mes, 2),
                "mermas": round(mermas_mes, 2),
                "inyecciones": round(inyecciones_mes, 2),
                "gastos_fondos": round(gastos_fondos_mes, 2),
                "ganancia_neta": round(ganancia_neta_mes, 2),
                "saldo_caja_mes": round(saldo_caja_mes, 2),
                "flujo_por_metodo": flujo_por_metodo,
                "gastos_por_metodo": gastos_por_metodo
            },
            "historial_mensual": historial_mensual,
            "historial_diario": historial_diario,
            "total_ventas": round(ventas_mes, 2),
            "total_invertido": round(gastos_operativos + inversiones_mes + compras_inventario, 2),
            "total_merma": round(mermas_mes, 2),
            "ganancia_bruta": round(ganancia_neta_mes, 2)
        }), 200

    except Exception as e:
        current_app.logger.exception("Excepción en get_dashboard: %s", e)
        return jsonify({"error": "Error interno en dashboard"}), 500


@dashboard_bp.route("/api/dashboard/tesoreria", methods=["GET"])
def get_tesoreria():
    try:
        s_id_filter = request.args.get("sucursal_id")
        is_global = not s_id_filter or s_id_filter == "global"

        where_global = "" if is_global else "WHERE sucursal_id = :s_id"
        params_global = {} if is_global else {"s_id": s_id_filter}

        # Caja Real Acumulada (Toda la historia / Tesorería) - a demanda, fuera de /api/dashboard
        sql_caja_total = f"SELECT SUM(CASE WHEN tipo = 'entrada' THEN monto ELSE -monto END) as saldo FROM movimientos_caja {where_global}"
        res_caja_total = fetch_one(sql_caja_total, params_global)
        saldo_caja_total_historico = to_number(res_caja_total.get("saldo", 0))

        return jsonify({"saldo_caja": round(saldo_caja_total_historico, 2)}), 200

    except Exception as e:
        current_app.logger.exception("Excepción en get_tesoreria: %s", e)
        return jsonify({"error": "Error interno en tesorería"}), 500


@dashboard_bp.route("/api/dashboard/historial-diario-mes", methods=["GET"])
def get_historial_diario_mes():
    try:
        mes = request.args.get("mes", "")
        if len(mes) != 7 or mes[4] != "-" or not mes[:4].isdigit() or not mes[5:].isdigit():
            return jsonify({"error": "Parámetro 'mes' inválido, use formato YYYY-MM"}), 400

        anio, mes_num = int(mes[:4]), int(mes[5:])
        if mes_num < 1 or mes_num > 12:
            return jsonify({"error": "Parámetro 'mes' inválido, use formato YYYY-MM"}), 400

        inicio_mes = date(anio, mes_num, 1).isoformat()
        fin_mes = (date(anio + 1, 1, 1) if mes_num == 12 else date(anio, mes_num + 1, 1)).isoformat()

        s_id_filter = request.args.get("sucursal_id")
        is_global = not s_id_filter or s_id_filter == "global"

        where_rango_mes = "WHERE fecha >= :inicio_mes AND fecha < :fin_mes" + (" AND sucursal_id = :s_id" if not is_global else "")
        params_rango_mes = {"inicio_mes": inicio_mes, "fin_mes": fin_mes}
        if not is_global:
            params_rango_mes["s_id"] = s_id_filter

        sql_dias_del_mes = f"""
            SELECT
                TO_CHAR(fecha, 'YYYY-MM-DD') as dia,
                SUM(total_pedido) as total_ventas
            FROM pedidos
            {where_rango_mes}
            GROUP BY dia
            ORDER BY dia DESC
        """
        dias = [
            {**d, "total_ventas": to_number(d["total_ventas"])}
            for d in fetch_all(sql_dias_del_mes, params_rango_mes)
        ]

        return jsonify(dias), 200

    except Exception as e:
        current_app.logger.exception("Excepción en get_historial_diario_mes: %s", e)
        return jsonify({"error": "Error interno en historial diario del mes"}), 500
