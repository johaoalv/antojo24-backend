from flask import Blueprint, jsonify
from datetime import date, timedelta
from supabase import create_client
import os

dashboard_bp = Blueprint("dashboard", __name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

@dashboard_bp.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    fecha_hoy = str(date.today())
    fecha_ayer = str(date.today() - timedelta(days=1))

    response_pedidos = supabase.table("pedidos").select("total_pedido, fecha, metodo_pago").execute()
    response_productos = supabase.table("productos_pedido").select("producto, cantidad").execute()

    if not response_pedidos.data or not response_productos.data:
        return jsonify({"error": "Error al obtener datos del dashboard"}), 500

    pedidos = response_pedidos.data
    productos = response_productos.data

    ventas_hoy = sum(p["total_pedido"] for p in pedidos if p["fecha"] == fecha_hoy)
    ventas_ayer = sum(p["total_pedido"] for p in pedidos if p["fecha"] == fecha_ayer)

    productos_vendidos = {}
    for p in productos:
        productos_vendidos[p["producto"]] = productos_vendidos.get(p["producto"], 0) + p["cantidad"]

    producto_mas_vendido = max(productos_vendidos, key=productos_vendidos.get) if productos_vendidos else "N/A"

    metodos_pago = {}
    for p in pedidos:
        metodos_pago[p["metodo_pago"]] = metodos_pago.get(p["metodo_pago"], 0) + 1

    metodo_pago_mas_usado = max(metodos_pago, key=metodos_pago.get) if metodos_pago else "N/A"

    variacion_porcentaje = ((ventas_hoy - ventas_ayer) / ventas_ayer * 100) if ventas_ayer > 0 else 100

    return jsonify({
        "ventas_hoy": ventas_hoy,
        "ventas_ayer": ventas_ayer,
        "producto_mas_vendido": producto_mas_vendido,
        "metodo_pago_mas_usado": metodo_pago_mas_usado,
        "variacion_porcentaje": round(variacion_porcentaje, 2)
    }), 200
