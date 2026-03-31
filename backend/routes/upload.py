import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename

upload_bp = Blueprint("upload", __name__)

# Configuración
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'antojo24-frontend', 'frontend', 'public', 'assets', 'productos')

# Crear carpeta si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@upload_bp.route("/upload", methods=["POST"])
def upload_file():
    try:
        # Verificar que hay archivo
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": f"Tipo de archivo no permitido. Usa: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

        # Generar nombre seguro
        filename = secure_filename(file.filename)
        # Agregar timestamp para evitar conflictos
        import uuid
        filename = f"{uuid.uuid4().hex}_{filename}"

        # Guardar archivo
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # Retornar ruta relativa para usar en el frontend
        relative_path = f"/assets/productos/{filename}"

        current_app.logger.info(f"✅ Imagen subida: {relative_path}")

        return jsonify({
            "success": True,
            "path": relative_path,
            "filename": filename
        }), 201

    except Exception as e:
        current_app.logger.error(f"Error al subir imagen: {e}")
        return jsonify({"error": str(e)}), 500
