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

        # 1. Obtener todas las tiendas (para el desglose o selector)
        sql_tiendas = "SELECT nombre_tienda, sucursal_id FROM tiendas_acceso"
        tiendas = fetch_all(sql_tiendas)
        
        nombre_sucursal = "Global"
        if not is_global:
            tienda_actual = next((t for t in tiendas if t["sucursal_id"] == s_id_filter), None)
            if tienda_actual:
                nombre_sucursal = tienda_actual["nombre_tienda"]

        # 2. Totales (Filtrados si no es global)
        where_clause = "" if is_global else "WHERE sucursal_id = :s_id"
        params = {} if is_global else {"s_id": s_id_filter}

        sql_ventas = f"SELECT SUM(total_pedido) as total FROM pedidos {where_clause}"
        res_ventas = fetch_one(sql_ventas, params)
        total_ventas = to_number(res_ventas.get("total", 0)) if res_ventas else 0.0

        sql_inversion = f"SELECT SUM(monto) as total FROM inversiones {where_clause}"
        res_inversion = fetch_one(sql_inversion, params)
        total_invertido = to_number(res_inversion.get("total", 0)) if res_inversion else 0.0

        # 3. Datos agrupados por sucursal (para el desglose interno si es global)
        desglose_tiendas = []
        if is_global:
            sql_v_suc = "SELECT sucursal_id, SUM(total_pedido) as total FROM pedidos GROUP BY sucursal_id"
            ventas_sucursal = {v["sucursal_id"]: to_number(v["total"]) for v in fetch_all(sql_v_suc)}

            sql_i_suc = "SELECT sucursal_id, SUM(monto) as total FROM inversiones GROUP BY sucursal_id"
            inversiones_sucursal = {i["sucursal_id"]: to_number(i["total"]) for i in fetch_all(sql_i_suc)}

            for t in tiendas:
                sid = t["sucursal_id"]
                v_t = ventas_sucursal.get(sid, 0.0)
                i_t = inversiones_sucursal.get(sid, 0.0)
                desglose_tiendas.append({
                    "nombre": t["nombre_tienda"],
                    "sucursal_id": sid,
                    "total_ventas": round(v_t, 2),
                    "total_invertido": round(i_t, 2),
                    "ganancia_bruta": round(v_t - i_t, 2)
                })

        # 4. Historial de Ventas Diario (Filtrado si no es global)
        sql_historial = f"""
            SELECT 
                SUBSTR(fecha::text, 1, 10) as dia,
                SUM(total_pedido) as total_ventas,
                SUM(CASE WHEN lower(metodo_pago) = 'efectivo' THEN total_pedido ELSE 0 END) as efectivo,
                SUM(CASE WHEN lower(metodo_pago) = 'tarjeta' THEN total_pedido ELSE 0 END) as tarjeta,
                SUM(CASE WHEN lower(metodo_pago) IN ('yappy', 'transferencia') THEN total_pedido ELSE 0 END) as yappy
            FROM pedidos
            {where_clause}
            GROUP BY dia
            ORDER BY dia DESC
            LIMIT 30
        """
        historial_raw = fetch_all(sql_historial, params)

        # 5. Cierres de caja
        sql_cierres = f"SELECT fecha_cierre::text as dia, SUM(total_real) as total_real FROM cierres_caja {where_clause} GROUP BY dia"
        cierres = {fecha_solo(c["dia"]): to_number(c["total_real"]) for c in fetch_all(sql_cierres, params)}

        historial_completo = []
        for v in historial_raw:
            dia = v["dia"]
            historial_completo.append({
                "fecha": dia,
                "total_ventas": to_number(v["total_ventas"]),
                "efectivo": to_number(v["efectivo"]),
                "tarjeta": to_number(v["tarjeta"]),
                "yappy": to_number(v["yappy"]),
                "total_cierre": cierres.get(dia, 0.0)
            })

        return jsonify({
            "nombre_sucursal": nombre_sucursal,
            "total_ventas": round(total_ventas, 2),
            "total_invertido": round(total_invertido, 2),
            "ganancia_bruta": round(total_ventas - total_invertido, 2),
            "historial": historial_completo,
            "por_tienda": desglose_tiendas
        }), 200

    except Exception as e:
        current_app.logger.exception("Excepción en get_dashboard: %s", e)
        return jsonify({"error": "Error interno en dashboard"}), 500
