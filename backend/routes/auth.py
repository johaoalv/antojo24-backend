from flask import Blueprint, request, jsonify
from db import fetch_one

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.json
    pin = data.get("pin")
    ip_cliente = data.get("ip_cliente")

    if not pin:
        return jsonify({"error": "PIN es requerido."}), 400

    # 1️⃣ Buscar la tienda por PIN
    sql = "SELECT id, nombre_tienda, sucursal_id, pin_acceso, rol, ip_permitida FROM tiendas_acceso WHERE pin_acceso = :pin LIMIT 1"
    tienda = fetch_one(sql, {"pin": pin})

    if not tienda:
        return jsonify({"error": "Pin incorrecto o tienda no encontrada."}), 404

    # 2️⃣ Validar IP
    ip_permitida = tienda.get("ip_permitida")
    if ip_permitida and ip_cliente != ip_permitida:
        print(f"[DEBUG LOGIN] Acceso denegado desde IP {ip_cliente} (permitida: {ip_permitida})")
        return jsonify({"error": "Acceso denegado: IP no autorizada"}), 403

    # 3️⃣ Respuesta exitosa
    return jsonify({
        "message": "Inicio de sesión exitoso ✅",
        "nombre_tienda": tienda["nombre_tienda"],
        "sucursal_id": tienda["sucursal_id"],
        "rol": tienda["rol"]
    }), 200
