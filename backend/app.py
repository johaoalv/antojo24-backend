from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_URL", "*")}})

# Registrar Blueprints
from routes.auth import auth_bp
from routes.pedido import pedido_bp
from routes.dashboard import dashboard_bp

app.register_blueprint(auth_bp)
app.register_blueprint(pedido_bp)
app.register_blueprint(dashboard_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
