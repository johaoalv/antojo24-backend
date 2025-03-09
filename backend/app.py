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

@app.route("/api/pedido", methods=["POST"])
def pedido():
    data = request.json
    print("Datos recibidos en el backend:", data)

    # Obtener variables de entorno de forma segura
    url_webhook_pedido = os.getenv("N8N_WEBHOOK_URL")
    api_key = os.getenv("N8N_API_KEY")

    # Verificar que las variables están definidas
    if not url_webhook_pedido or not api_key:
        return jsonify({"error": "Faltan variables de entorno en el servidor"}), 500

    # Configurar headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key
    }

    # Enviar datos a n8n
    response = requests.post(url_webhook_pedido, headers=headers, json=data)
    return response.text, response.status_code  # Devuelve la respuesta de n8n

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
