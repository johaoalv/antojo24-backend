
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
        # 1. Calcular Inversión en Stock (Actual)
        sql_inversion = "SELECT SUM(stock * costo_unidad) as inversion FROM insumos"
        res_inversion = fetch_one(sql_inversion)
        inversion_actual = to_number(res_inversion.get("inversion", 0)) if res_inversion else 0.0

        # 2. Obtener Historial de Ventas Agrupado por Fecha
        # Nota: Usamos SUBSTRING para la fecha si es un timestamp string
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

        # 3. Obtener Cierres de Caja para comparar
        sql_cierres = """
            SELECT fecha_cierre::text as dia, total_real
            FROM cierres_caja
        """
        cierres = {fecha_solo(c["dia"]): to_number(c["total_real"]) for c in fetch_all(sql_cierres)}

        # 4. Mezclar datos
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

        # 5. Producto más vendido (del último mes)
        sql_top_producto = """
            SELECT producto, SUM(cantidad) as total_cant
            FROM productos_pedido
            GROUP BY producto
            ORDER BY total_cant DESC
            LIMIT 1
        """
        res_top = fetch_one(sql_top_producto)
        producto_mas_vendido = res_top["producto"] if res_top else "N/A"

        return jsonify({
            "inversion_actual": round(inversion_actual, 2),
            "producto_mas_vendido": producto_mas_vendido,
            "historial": historial_completo
        }), 200

    except Exception as e:
        current_app.logger.exception("Excepción en get_dashboard: %s", e)
        return jsonify({"error": "Error interno en dashboard"}), 500
