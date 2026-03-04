from flask import Blueprint, jsonify, current_app, request
from datetime import date, timedelta
import os
from db import fetch_all, fetch_one

def to_number(v):
    if v is None: return 0.0
    try:
        return float(v)
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
        sql_ventas_mes = f"SELECT SUM(total_pedido) as total FROM pedidos {where_mes}"
        res_ventas_mes = fetch_one(sql_ventas_mes, params_mes)
        ventas_mes = to_number(res_ventas_mes.get("total", 0))

        # Gastos del mes (Operativos: todo menos 'inversion')
        sql_gastos_op = f"SELECT SUM(monto) as total FROM gastos {where_mes} AND categoria != 'inversion'"
        res_gastos_op = fetch_one(sql_gastos_op, params_mes)
        gastos_operativos = to_number(res_gastos_op.get("total", 0))

        # Inversiones del mes (Solo categoria 'inversion')
        sql_gastos_inv = f"SELECT SUM(monto) as total FROM gastos {where_mes} AND categoria = 'inversion'"
        res_gastos_inv = fetch_one(sql_gastos_inv, params_mes)
        inversiones_mes = to_number(res_gastos_inv.get("total", 0))

        # Mermas del mes
        sql_merma_mes = f"""
            SELECT COALESCE(SUM(m.cantidad * i.costo_unidad), 0) as total
            FROM mermas m
            JOIN insumos i ON m.insumo_id = i.id
            {where_mes.replace('fecha', 'm.fecha').replace('sucursal_id', 'm.sucursal_id')}
        """
        res_merma_mes = fetch_one(sql_merma_mes, params_mes)
        mermas_mes = to_number(res_merma_mes.get("total", 0))

        # Inyecciones del mes
        sql_iny_mes = f"SELECT SUM(monto) as total FROM inyecciones {where_mes}"
        res_iny_mes = fetch_one(sql_iny_mes, params_mes)
        inyecciones_mes = to_number(res_iny_mes.get("total", 0))

        # Ganancia Neta = Ventas - Gastos Operativos - Mermas
        ganancia_neta_mes = ventas_mes - gastos_operativos - mermas_mes

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
        historial_mensual = fetch_all(sql_historial_mes, params)

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
            LIMIT 15
        """
        historial_diario = fetch_all(sql_historial_diario, params)

        return jsonify({
            "nombre_sucursal": nombre_sucursal,
            "mes_actual": {
                "ventas": round(ventas_mes, 2),
                "gastos_operativos": round(gastos_operativos, 2),
                "inversiones": round(inversiones_mes, 2),
                "mermas": round(mermas_mes, 2),
                "inyecciones": round(inyecciones_mes, 2),
                "ganancia_neta": round(ganancia_neta_mes, 2)
            },
            "historial_mensual": historial_mensual,
            "historial_diario": historial_diario,
            "por_tienda": desglose_tiendas,
            "total_ventas": round(ventas_mes, 2),
            "total_invertido": round(gastos_operativos + inversiones_mes, 2),
            "total_merma": round(mermas_mes, 2),
            "ganancia_bruta": round(ganancia_neta_mes, 2)
        }), 200

    except Exception as e:
        current_app.logger.exception("Excepción en get_dashboard: %s", e)
        return jsonify({"error": "Error interno en dashboard"}), 500
