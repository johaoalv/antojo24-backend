from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from flask_cors import CORS

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


@app.route("/api/pedido", methods=["POST"])
def pedido():
     data = request.json
     print("Datos recibidos en el backend:", data)
     url_webhook_pedido = os.environ["N8N_WEBHOOK_URL"]  # URL del webhook de n8n
     headers = {
        "Content-Type": "application/json",
        "Authorization": os.environ["N8N_API_KEY"] 
    }
    
     response = requests.post(url_webhook_pedido, headers=headers, json=request.get_json())
     return response.text, response.status_code  # Devuelve la respuesta de n8n

if __name__ == "__main__":
    app.run(debug=True, port=5000)  # Ejecutar en el puerto 5000
