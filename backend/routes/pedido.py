from flask import Blueprint, request, jsonify # type: ignore
from supabase import create_client # type: ignore
import os

pedido_bp = Blueprint("pedido", __name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

@pedido_bp.route("/api/pedido", methods=["POST"])
def pedido():
    data = request.json
    productos = [
        {
            "pedido_id": item["pedido_id"],
            "producto": item["producto"],
            "cantidad": item["cantidad"],
            "total_item": item["total_item"],
            "total_pedido": data["total_pedido"],
            "metodo_pago": data["metodo_pago"],
        }
        for item in data["pedido"]
    ]

    response = supabase.table("productos_pedido").insert(productos).execute()

    if response.data:
        return jsonify({"message": "Pedido insertado correctamente en Supabase"}), 201
    else:
        return jsonify({"error": "Error al insertar en Supabase", "details": response}), 500

@pedido_bp.route("/api/pedido", methods=["OPTIONS"])
def handle_options():
    return '', 200
