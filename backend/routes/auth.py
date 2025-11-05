from flask import Blueprint, request, jsonify
from db import fetch_one

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.json
    pin = data.get("pin")

    if not pin:
        return jsonify({"error": " PIN son requeridos."}), 400

    sql = "SELECT id, nombre_tienda, sucursal_id, pin_acceso, rol FROM tiendas_acceso WHERE pin_acceso = :pin LIMIT 1"
    tienda = fetch_one(sql, {"pin": pin})

    if not tienda:
        return jsonify({"error": "Pin incorrecto o tienda no encontrada."}), 404

    return jsonify({
            "message": "Inicio de sesión exitoso",
            "nombre_tienda": tienda["nombre_tienda"],
            "sucursal_id": tienda["sucursal_id"],
            "rol": tienda["rol"]
        }), 200
 
