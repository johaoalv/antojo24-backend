from flask import Blueprint, request, jsonify # type: ignore
from supabase import create_client # type: ignore
import bcrypt # type: ignore
import os

auth_bp = Blueprint("auth", __name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def verify_pin(pin, hashed_pin):
    return bcrypt.checkpw(pin.encode(), hashed_pin.encode())

@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.json
    pin = data.get("pin")

    if not pin:
        return jsonify({"error": "Cédula y PIN son requeridos."}), 400

    response = supabase.table("empleados").select("nombre, apellido, pin").execute()

    if not response.data:
        return jsonify({"error": "Empleado no encontrado."}), 404

    empleado = response.data[0]
    if verify_pin(pin, empleado["pin"]):
        return jsonify({
            "message": "Inicio de sesión exitoso",
            "nombre": empleado["nombre"],
            "apellido": empleado["apellido"]
        }), 200
    else:
        return jsonify({"error": "PIN incorrecto."}), 401
