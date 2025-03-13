from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from flask_cors import CORS

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configurar CORS: Permite todos los orígenes en local, y en producción Netlify
CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_URL", "*")}})

# Variables de entorno para Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Endpoint para insertar en la tabla productos_pedido
@app.route("/api/pedido", methods=["POST"])
def pedido():
    data = request.json
    supabase_endpoint = f"{SUPABASE_URL}/rest/v1/productos_pedido"
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"
    }
    productos = [
        {
            "pedido_id": item["pedido_id"],
            "producto": item["producto"],
            "cantidad": item["cantidad"],
            "total_item": item["total_item"],
            "total_pedido": item["total_pedido"],
            "metodo_pago": item["metodo_pago"]
        }
        for item in data.get("productos_pedido", [])
    ]
    response = requests.post(supabase_endpoint, headers=headers, json=productos)
    return jsonify({"message": "Pedido insertado correctamente en Supabase"}) if response.status_code in [200, 201] else jsonify({"error": "Error al insertar en Supabase", "details": response.text}), response.status_code
# Manejo de preflight request para CORS en Netlify
@app.route("/api/pedido", methods=["OPTIONS"])
def handle_options():
    return '', 200

@app.route("/api/ventas-hoy", methods=["GET"])
def ventas_hoy():
    # Obtener la URL del webhook de n8n desde las variables de entorno
    url_webhook_ventas_hoy = os.getenv("N8N_VENTAS_HOY_URL")

    # Verificar que la variable está definida
    if not url_webhook_ventas_hoy:
        return jsonify({"error": "Falta la URL del webhook en el servidor"}), 500

    # Hacer la solicitud GET a n8n
    response = requests.get(url_webhook_ventas_hoy)

    return response.text, response.status_code  # Devuelve la respuesta de n8n directamente


# Configurar el puerto correctamente en local y Railway
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
