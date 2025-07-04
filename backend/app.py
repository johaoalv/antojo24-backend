from flask import Flask, request, abort
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {
    "origins": [
        os.getenv("NETLIFY_URL")
    ],
    "supports_credentials": True
}})



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

# @app.before_request
# def validar_origen():
#     origen_valido = "https://rapid-food-pma.netlify.app/"
#     origen = request.headers.get("Origin", "")
#     if origen and origen != origen_valido:
#         abort(403)

@app.after_request
def aplicar_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = os.getenv("NETLIFY_URL")
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
