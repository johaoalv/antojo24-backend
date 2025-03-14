from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from flask_cors import CORS
from supabase import create_client, Client

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configurar CORS: Permite todos los orígenes en local, y en producción Netlify
CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_URL", "*")}})

# Variables de entorno para Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
# Crear el cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
print(app.url_map)

# Endpoint para insertar en la tabla productos_pedido
@app.route("/api/pedido", methods=["POST"])
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

# Manejo de preflight request para CORS en Netlify
@app.route("/api/pedido", methods=["OPTIONS"])
def handle_options():
    return '', 200

@app.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    from datetime import date, timedelta

    fecha_hoy = str(date.today())  # Obtiene la fecha de hoy en formato YYYY-MM-DD
    fecha_ayer = str(date.today() - timedelta(days=1))  # Fecha de ayer

    # 🔹 Obtener TODOS los pedidos de Supabase
    response = supabase.table("pedidos") \
        .select("total_pedido, fecha") \
        .execute()

    if not response.data:
        return jsonify({"error": "Error al obtener datos de pedidos", "details": response}), 500

    pedidos = response.data

    # 🔹 Filtrar y calcular los totales en Python
    ventas_hoy = sum(p["total_pedido"] for p in pedidos if p["fecha"] == fecha_hoy)
    ventas_ayer = sum(p["total_pedido"] for p in pedidos if p["fecha"] == fecha_ayer)

    return jsonify({
        "ventas_hoy": ventas_hoy,
        "ventas_ayer": ventas_ayer
    }), 200


# Configurar el puerto correctamente en local y Railway
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
