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

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    try:
        # 0. Obtener parámetros de filtro
        s_id_filter = request.args.get("sucursal_id")
        is_global = not s_id_filter or s_id_filter == "global"

        # 1. Obtener todas las tiendas
        sql_tiendas = "SELECT nombre_tienda, sucursal_id FROM tiendas_acceso"
        tiendas = fetch_all(sql_tiendas)
        
        nombre_sucursal = "Global"
        if not is_global:
            tienda_actual = next((t for t in tiendas if t["sucursal_id"] == s_id_filter), None)
            if tienda_actual:
                nombre_sucursal = tienda_actual["nombre_tienda"]

        # 2. Cláusula de filtrado
        where_clause = "" if is_global else "WHERE sucursal_id = :s_id"
        params = {} if is_global else {"s_id": s_id_filter}

        # --- CÁLCULOS DEL MES ACTUAL ---
        hoy = date.today()
        inicio_mes = hoy.replace(day=1).isoformat()
        
        where_mes = f"WHERE fecha >= :inicio_mes" + (" AND sucursal_id = :s_id" if not is_global else "")
        params_mes = {"inicio_mes": inicio_mes}
        if not is_global:
            params_mes["s_id"] = s_id_filter

        # Ventas del mes
        sql_ventas_mes = f"SELECT SUM(total_pedido) as total, SUM(costo_total) as cogs FROM pedidos {where_mes}"
        res_ventas_mes = fetch_one(sql_ventas_mes, params_mes)
        ventas_mes = to_number(res_ventas_mes.get("total", 0))
        cogs_mes = to_number(res_ventas_mes.get("cogs", 0))

        # Gastos Operativos (salida / operativo)
        sql_gastos_op = f"SELECT SUM(monto) as total FROM movimientos_caja {where_mes} AND tipo = 'salida' AND categoria = 'operativo'"
        res_gastos_op = fetch_one(sql_gastos_op, params_mes)
        gastos_operativos = to_number(res_gastos_op.get("total", 0))

        # Compras de Inventario (salida / inventario)
        sql_gastos_inv_compras = f"SELECT SUM(monto) as total FROM movimientos_caja {where_mes} AND tipo = 'salida' AND categoria = 'inventario'"
        res_gastos_inv_compras = fetch_one(sql_gastos_inv_compras, params_mes)
        compras_inventario = to_number(res_gastos_inv_compras.get("total", 0))

        # Inversiones (salida / inversion) - Nota: a veces inversion es entrada, pero aqui buscamos el gasto de inversion si aplica
        sql_gastos_inv = f"SELECT SUM(monto) as total FROM movimientos_caja {where_mes} AND tipo = 'salida' AND categoria = 'inversion'"
        res_gastos_inv = fetch_one(sql_gastos_inv, params_mes)
        inversiones_mes = to_number(res_gastos_inv.get("total", 0))

        # Inyecciones (entrada / inversion)
        sql_iny_mes = f"SELECT SUM(monto) as total FROM movimientos_caja {where_mes} AND tipo = 'entrada' AND categoria = 'inversion'"
        res_iny_mes = fetch_one(sql_iny_mes, params_mes)
        inyecciones_mes = to_number(res_iny_mes.get("total", 0))

        # Mermas del mes (estas no son movimientos de caja físicos, son pérdida de valor de inventario)
        sql_merma_mes = f"""
            SELECT COALESCE(SUM(m.cantidad * i.costo_unidad), 0) as total
            FROM mermas m
            JOIN insumos i ON m.insumo_id = i.id
            {where_mes.replace('fecha', 'm.fecha').replace('sucursal_id', 'm.sucursal_id')}
        """
        res_merma_mes = fetch_one(sql_merma_mes, params_mes)
        mermas_mes = to_number(res_merma_mes.get("total", 0))

        # --- CALCULO DE UTILIDAD ACUMULADA (HISTÓRICA) ---
        where_global = "" if is_global else "WHERE sucursal_id = :s_id"
        params_global = {} if is_global else {"s_id": s_id_filter}

        # 1. Ventas y COGS Histórico
        sql_hist_ventas = f"SELECT SUM(total_pedido) as total, SUM(costo_total) as cogs FROM pedidos {where_global}"
        res_hist_ventas = fetch_one(sql_hist_ventas, params_global)
        hist_ventas = to_number(res_hist_ventas.get("total", 0))
        hist_cogs = to_number(res_hist_ventas.get("cogs", 0))

        # 2. Gastos Operativos Históricos
        sql_hist_gastos = f"SELECT SUM(monto) as total FROM movimientos_caja {where_global} {'AND' if not is_global else 'WHERE'} tipo = 'salida' AND categoria = 'operativo'"
        res_hist_gastos = fetch_one(sql_hist_gastos, params_global)
        hist_gastos_op = to_number(res_hist_gastos.get("total", 0))

        # 3. Mermas Históricas
        sql_hist_mermas = f"""
            SELECT COALESCE(SUM(m.cantidad * i.costo_unidad), 0) as total
            FROM mermas m
            JOIN insumos i ON m.insumo_id = i.id
            {where_global.replace('sucursal_id', 'm.sucursal_id')}
        """
        res_hist_mermas = fetch_one(sql_hist_mermas, params_global)
        hist_mermas = to_number(res_hist_mermas.get("total", 0))

        utilidad_acumulada_total = hist_ventas - hist_cogs - hist_gastos_op - hist_mermas

        # Caja Real Acumulada (Toda la historia / Plata Real)
        sql_caja_total = f"SELECT SUM(CASE WHEN tipo = 'entrada' THEN monto ELSE -monto END) as saldo FROM movimientos_caja {where_global}"
        res_caja_total = fetch_one(sql_caja_total, params_global)
        saldo_caja_total_historico = to_number(res_caja_total.get("saldo", 0))

        # --- LOGICA FINANCIERA DEL MES (Ya existente) ---
        ganancia_neta_mes = ventas_mes - cogs_mes - gastos_operativos - mermas_mes

        # Caja del MES (Solo flujo del período actual)
        sql_caja_mes = f"SELECT SUM(CASE WHEN tipo = 'entrada' THEN monto ELSE -monto END) as saldo FROM movimientos_caja {where_mes}"
        res_caja_mes = fetch_one(sql_caja_mes, params_mes)
        saldo_caja_mes = to_number(res_caja_mes.get("saldo", 0))

        # --- HISTORIAL MENSUAL ---
        sql_historial_mes = f"""
            SELECT 
                SUBSTR(fecha::text, 1, 7) as mes,
                SUM(total_pedido) as total_ventas
            FROM pedidos
            {where_clause}
            GROUP BY mes
            ORDER BY mes DESC
            LIMIT 12
        """
        historial_mensual = [
            {**h, "total_ventas": to_number(h["total_ventas"])}
            for h in fetch_all(sql_historial_mes, params)
        ]

        # --- DESGLOSE POR TIENDA (Solo si es global) ---
        desglose_tiendas = []
        if is_global:
            sql_v_suc = "SELECT sucursal_id, SUM(total_pedido) as total FROM pedidos GROUP BY sucursal_id"
            ventas_sucursal = {v["sucursal_id"]: to_number(v["total"]) for v in fetch_all(sql_v_suc)}

            sql_g_suc = "SELECT sucursal_id, SUM(monto) as total FROM gastos GROUP BY sucursal_id"
            gastos_sucursal = {i["sucursal_id"]: to_number(i["total"]) for i in fetch_all(sql_g_suc)}

            for t in tiendas:
                sid = t["sucursal_id"]
                v_t = ventas_sucursal.get(sid, 0.0)
                g_t = gastos_sucursal.get(sid, 0.0)
                desglose_tiendas.append({
                    "nombre": t["nombre_tienda"],
                    "sucursal_id": sid,
                    "total_ventas": round(v_t, 2),
                    "total_gastos": round(g_t, 2),
                    "balance": round(v_t - g_t, 2)
                })

        # --- HISTORIAL DIARIO (Mantener para compatibilidad actual) ---
        sql_historial_diario = f"""
            SELECT 
                SUBSTR(fecha::text, 1, 10) as dia,
                SUM(total_pedido) as total_ventas
            FROM pedidos
            {where_clause}
            GROUP BY dia
            ORDER BY dia DESC
            LIMIT 100
        """
        historial_diario = [
            {**d, "total_ventas": to_number(d["total_ventas"])}
            for d in fetch_all(sql_historial_diario, params)
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
                "ganancia_neta": round(ganancia_neta_mes, 2),
                "saldo_caja": round(saldo_caja_total_historico, 2),
                "saldo_caja_mes": round(saldo_caja_mes, 2),
                "utilidad_acumulada": round(utilidad_acumulada_total, 2)
            },
            "historial_mensual": historial_mensual,
            "historial_diario": historial_diario,
            "por_tienda": desglose_tiendas,
            "total_ventas": round(ventas_mes, 2),
            "total_invertido": round(gastos_operativos + inversiones_mes + compras_inventario, 2),
            "total_merma": round(mermas_mes, 2),
            "ganancia_bruta": round(ganancia_neta_mes, 2)
        }), 200

    except Exception as e:
        current_app.logger.exception("Excepción en get_dashboard: %s", e)
        return jsonify({"error": "Error interno en dashboard"}), 500
