from flask import Blueprint, jsonify, request
from db import fetch_all, fetch_one, execute, insert_many
import logging

productos_bp = Blueprint("productos", __name__, url_prefix="/api/productos")

@productos_bp.route("/", methods=["GET"])
def get_productos():
    try:
        # Obtener todos los productos
        productos = fetch_all("SELECT * FROM productos ORDER BY id ASC")
        return jsonify(productos), 200
    except Exception as e:
        logging.error(f"Error al obtener productos: {e}")
        return jsonify({"error": str(e)}), 500

@productos_bp.route("/<int:id>", methods=["GET"])
def get_producto(id):
    try:
        producto = fetch_one("SELECT * FROM productos WHERE id = :id", {"id": id})
        if not producto:
            return jsonify({"error": "Producto no encontrado"}), 404
        return jsonify(producto), 200
    except Exception as e:
        logging.error(f"Error al obtener producto {id}: {e}")
        return jsonify({"error": str(e)}), 500

@productos_bp.route("/", methods=["POST"])
def create_producto():
    try:
        data = request.json
        if not data or "nombre" not in data or "precio" not in data:
            return jsonify({"error": "Faltan campos requeridos (nombre, precio)"}), 400

        # Importante: convertir el JSON a string si es necesario, psycopg2 o sqlalchemy deberían manejar dict a jsonb
        import json
        combo_items = json.dumps(data.get("combo_items", []))
        
        sql = """
            INSERT INTO productos (nombre, precio, imagen, es_combo, combo_items)
            VALUES (:nombre, :precio, :imagen, :es_combo, :combo_items)
            RETURNING id
        """
        params = {
            "nombre": data["nombre"],
            "precio": data["precio"],
            "imagen": data.get("imagen", ""),
            "es_combo": data.get("es_combo", False),
            "combo_items": combo_items
        }
        
        # Como execute devuelve rowcount, usamos fetch_one para obtener el ID de retorno
        nuevo_id_row = fetch_one(sql, params)
        if nuevo_id_row:
             return jsonify({"message": "Producto creado exitosamente", "id": nuevo_id_row["id"]}), 201
        return jsonify({"error": "No se pudo crear el producto"}), 500
        
    except Exception as e:
        logging.error(f"Error al crear producto: {e}")
        return jsonify({"error": str(e)}), 500

@productos_bp.route("/<int:id>", methods=["PUT"])
def update_producto(id):
    try:
        data = request.json
        if not data:
             return jsonify({"error": "No hay datos para actualizar"}), 400

        # Verificar que existe
        producto = fetch_one("SELECT id FROM productos WHERE id = :id", {"id": id})
        if not producto:
            return jsonify({"error": "Producto no encontrado"}), 404

        import json
        
        updates = []
        params = {"id": id}
        
        if "nombre" in data:
            updates.append("nombre = :nombre")
            params["nombre"] = data["nombre"]
        if "precio" in data:
            updates.append("precio = :precio")
            params["precio"] = data["precio"]
        if "imagen" in data:
            updates.append("imagen = :imagen")
            params["imagen"] = data["imagen"]
        if "es_combo" in data:
            updates.append("es_combo = :es_combo")
            params["es_combo"] = data["es_combo"]
        if "combo_items" in data:
            updates.append("combo_items = :combo_items")
            params["combo_items"] = json.dumps(data["combo_items"])

        if not updates:
            return jsonify({"message": "No hay campos válidos para actualizar"}), 400

        sql = f"UPDATE productos SET {', '.join(updates)} WHERE id = :id"
        execute(sql, params)
        
        return jsonify({"message": "Producto actualizado exitosamente"}), 200
        
    except Exception as e:
        logging.error(f"Error al actualizar producto {id}: {e}")
        return jsonify({"error": str(e)}), 500

@productos_bp.route("/<int:id>", methods=["DELETE"])
def delete_producto(id):
    try:
        # Verificar que existe
        producto = fetch_one("SELECT id FROM productos WHERE id = :id", {"id": id})
        if not producto:
            return jsonify({"error": "Producto no encontrado"}), 404

        execute("DELETE FROM productos WHERE id = :id", {"id": id})
        return jsonify({"message": "Producto eliminado exitosamente"}), 200
        
    except Exception as e:
        logging.error(f"Error al eliminar producto {id}: {e}")
        return jsonify({"error": str(e)}), 500

# Endpoint especial para cargar productos del JSON original a la base de datos (solo la primera vez)
@productos_bp.route("/migrar", methods=["POST"])
def migrar_productos():
    try:
        data = request.json # Espera la lista de productos
        if not isinstance(data, list):
             return jsonify({"error": "Se esperaba una lista JSON"}), 400
             
        # Limpiar antes si se desea? o solo insertar. En este caso, limpiamos pa evitar dup
        execute("TRUNCATE TABLE productos RESTART IDENTITY")
        import json
        inserted = 0
        for p in data:
            sql = """
                INSERT INTO productos (nombre, precio, imagen, es_combo, combo_items)
                VALUES (:nombre, :precio, :imagen, :es_combo, :combo_items)
            """
            params = {
                "nombre": p.get("producto", ""),
                "precio": p.get("precio", 0),
                "imagen": p.get("imagen", ""),
                "es_combo": False,
                "combo_items": json.dumps([])
            }
            execute(sql, params)
            inserted += 1
            
        return jsonify({"message": f"Migrados {inserted} productos"}), 200

    except Exception as e:
        logging.error(f"Error en migracion: {e}")
        return jsonify({"error": str(e)}), 500
