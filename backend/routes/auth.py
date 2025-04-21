from flask import Blueprint, request, jsonify # type: ignore
from supabase import create_client # type: ignore
import os

auth_bp = Blueprint("auth", __name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.json
    pin = data.get("pin")

    if not pin:
        return jsonify({"error": " PIN son requeridos."}), 400

    response = supabase.table("tiendas_acceso").select("id, nombre_tienda, sucursal_id, pin_acceso, rol").eq("pin_acceso", pin).execute()


    if not response.data:
        return jsonify({"error": "Pin incorrecto o tienda no encontrada."}), 404

    tienda = response.data[0]
    return jsonify({
            "message": "Inicio de sesión exitoso",
            "nombre_tienda": tienda["nombre_tienda"],
            "sucursal_id": tienda["sucursal_id"],
            "rol": tienda["rol"]
        }), 200
 
