
from flask import Blueprint, jsonify, current_app
from datetime import date, timedelta
import os
from db import fetch_all

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    try:
        fecha_hoy = str(date.today())
        fecha_ayer = str(date.today() - timedelta(days=1))

        # obtener pedidos y productos desde la DB con joins apropiados
        sql_pedidos = """
            SELECT p.total_pedido, p.fecha, p.metodo_pago 
            FROM pedidos p 
            WHERE p.fecha >= :fecha_ayer
        """
        
        sql_productos = """
            SELECT pp.producto, pp.cantidad 
            FROM productos_pedido pp
            JOIN pedidos p ON p.pedido_id = pp.pedido_id
            WHERE p.fecha >= :fecha_inicio_mes
        """
        
        try:
            # Obtener pedidos de hoy y ayer
            pedidos = fetch_all(sql_pedidos, {
                "fecha_ayer": fecha_ayer
            })
            
            # Obtener productos del último mes para estadísticas
            productos = fetch_all(sql_productos, {
                "fecha_inicio_mes": str(date.today().replace(day=1))
            })
            
            if pedidos is None or productos is None:
                current_app.logger.error("Error al consultar la base de datos para dashboard")
                return jsonify({"error": "Error al obtener datos del dashboard"}), 500
                
        except Exception as db_error:
            current_app.logger.error("Error en consulta de dashboard: %s", db_error)
            return jsonify({"error": "Error al obtener datos del dashboard"}), 500

        # normalizar y calcular ventas (fecha puede contener hora, tomamos la parte YYYY-MM-DD)
        def fecha_solo(f):
            if not f:
                return ""
            return str(f)[:10]

        def to_number(v):
            try:
                return float(v)
            except Exception:
                return 0.0

        ventas_hoy = sum(to_number(p.get("total_pedido", 0)) for p in pedidos if fecha_solo(p.get("fecha")) == fecha_hoy)
        ventas_ayer = sum(to_number(p.get("total_pedido", 0)) for p in pedidos if fecha_solo(p.get("fecha")) == fecha_ayer)

        productos_vendidos = {}
        for p in productos:
            prod = p.get("producto")
            cant = p.get("cantidad", 0) or 0
            try:
                cant = int(cant)
            except Exception:
                try:
                    cant = int(float(cant))
                except Exception:
                    cant = 0
            if prod:
                productos_vendidos[prod] = productos_vendidos.get(prod, 0) + cant

        producto_mas_vendido = max(productos_vendidos, key=productos_vendidos.get) if productos_vendidos else "N/A"

        metodos_pago = {}
        for p in pedidos:
            metodo = p.get("metodo_pago") or "unknown"
            metodos_pago[metodo] = metodos_pago.get(metodo, 0) + 1

        metodo_pago_mas_usado = max(metodos_pago, key=metodos_pago.get) if metodos_pago else "N/A"

        variacion_porcentaje = ((ventas_hoy - ventas_ayer) / ventas_ayer * 100) if ventas_ayer > 0 else 100

        return jsonify({
            "ventas_hoy": ventas_hoy,
            "ventas_ayer": ventas_ayer,
            "producto_mas_vendido": producto_mas_vendido,
            "metodo_pago_mas_usado": metodo_pago_mas_usado,
            "variacion_porcentaje": round(variacion_porcentaje, 2)
        }), 200

    except Exception as e:
        current_app.logger.exception("Excepción en get_dashboard: %s", e)
        return jsonify({"error": "Error interno en dashboard"}), 500
