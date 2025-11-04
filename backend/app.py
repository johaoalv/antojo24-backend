from gevent import monkey
monkey.patch_all()
from flask import Flask, request, abort, jsonify
from flask_cors import CORS
from socket_instance import socketio, emit
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
allowed_origins = [os.getenv("NETLIFY_URL"), "http://localhost:5173"]
CORS(app, resources={r"/api/*": {
    "origins": allowed_origins,
    "supports_credentials": True
}})

# Inicializar SocketIO
socketio.init_app(app, async_mode="gevent", cors_allowed_origins=allowed_origins)




# Registrar Blueprints
from routes.auth import auth_bp
from routes.pedido import pedido_bp
from routes.dashboard import dashboard_bp
from routes.print import print_bp
from routes.cierre import cierre_bp

app.register_blueprint(auth_bp)
app.register_blueprint(pedido_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(print_bp)
app.register_blueprint(cierre_bp)

@app.after_request
def aplicar_cors_headers(response):
    origin = request.headers.get('Origin')
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


# Evento al conectar
@socketio.on("connect")
def handle_connect():
    print("🟢 Cliente conectado vía WebSocket")
    emit("server_msg", {"msg": "Conexión exitosa con Flask WebSocket"})

# 🔁 Reemplazamos app.run por socketio.run
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
