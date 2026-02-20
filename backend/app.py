from gevent import monkey
monkey.patch_all()
from flask import Flask, request, abort, jsonify
import logging
from flask_cors import CORS
from socket_instance import socketio, emit
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
allowed_origins = [
    os.getenv("NETLIFY_URL"), 
    os.getenv("FRONTEND_URL")
]
allowed_origins = [o for o in allowed_origins if o]

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
from routes.insumos import insumos_bp
from routes.inversiones import inversiones_bp
from routes.produccion import produccion_bp
from routes.costeo import costeo_bp
from routes.recetas import recetas_bp
from routes.mermas import mermas_bp

app.register_blueprint(auth_bp)
app.register_blueprint(pedido_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(print_bp)
app.register_blueprint(cierre_bp)
app.register_blueprint(insumos_bp)
app.register_blueprint(inversiones_bp)
app.register_blueprint(produccion_bp)
app.register_blueprint(costeo_bp)
app.register_blueprint(recetas_bp)
app.register_blueprint(mermas_bp)

@app.after_request
def aplicar_cors_headers(response):
    origin = request.headers.get('Origin')
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    # Log request + response summary so it's visible in the server console
    try:
        app.logger.debug("%s %s -> %s (Origin=%s)", request.method, request.path, response.status, request.headers.get('Origin'))
    except Exception:
        # don't raise logging errors
        pass
    return response


@app.before_request
def log_incoming_request():
    # Log method/path and a short preview of the body for debugging
    try:
        body = None
        if request.method in ("POST", "PUT", "PATCH"):
            body = request.get_data(as_text=True)
            if body and len(body) > 1000:
                body = body[:1000] + "...[truncated]"
        app.logger.debug("Incoming request: %s %s Origin=%s Body=%s", request.method, request.path, request.headers.get('Origin'), body)
    except Exception:
        pass


# Evento al conectar
@socketio.on("connect")
def handle_connect():
    print("🟢 Cliente conectado vía WebSocket")
    emit("server_msg", {"msg": "Conexión exitosa con Flask WebSocket"})

# 🔁 Reemplazamos app.run por socketio.run
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
