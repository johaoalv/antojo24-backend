
from flask import Blueprint, jsonify, current_app
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
        # 1. Total Ventas (Histórico)
        sql_total_ventas = "SELECT SUM(total_pedido) as total FROM pedidos"
        res_ventas = fetch_one(sql_total_ventas)
        total_ventas = to_number(res_ventas.get("total", 0)) if res_ventas else 0.0

        # 2. Total Invertido (Manual)
        sql_total_inversion = "SELECT SUM(monto) as total FROM inversiones"
        res_inversion = fetch_one(sql_total_inversion)
        total_invertido = to_number(res_inversion.get("total", 0)) if res_inversion else 0.0

        # 3. Ganancia Bruta
        ganancia_bruta = total_ventas - total_invertido

        # 4. Obtener Historial de Ventas Agrupado por Fecha (Para la nueva página de Ventas)
        sql_ventas_historial = """
            SELECT 
                SUBSTR(fecha::text, 1, 10) as dia,
                SUM(total_pedido) as total_ventas,
                SUM(CASE WHEN lower(metodo_pago) = 'efectivo' THEN total_pedido ELSE 0 END) as efectivo,
                SUM(CASE WHEN lower(metodo_pago) = 'tarjeta' THEN total_pedido ELSE 0 END) as tarjeta,
                SUM(CASE WHEN lower(metodo_pago) IN ('yappy', 'transferencia') THEN total_pedido ELSE 0 END) as yappy
            FROM pedidos
            GROUP BY dia
            ORDER BY dia DESC
            LIMIT 30
        """
        historial_ventas = fetch_all(sql_ventas_historial)

        # 5. Obtener Cierres de Caja para comparar
        sql_cierres = """
            SELECT fecha_cierre::text as dia, total_real
            FROM cierres_caja
        """
        cierres = {fecha_solo(c["dia"]): to_number(c["total_real"]) for c in fetch_all(sql_cierres)}

        # 6. Mezclar datos de historial
        historial_completo = []
        for v in historial_ventas:
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
            "total_ventas": round(total_ventas, 2),
            "total_invertido": round(total_invertido, 2),
            "ganancia_bruta": round(ganancia_bruta, 2),
            "historial": historial_completo
        }), 200

    except Exception as e:
        current_app.logger.exception("Excepción en get_dashboard: %s", e)
        return jsonify({"error": "Error interno en dashboard"}), 500
