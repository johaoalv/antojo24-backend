from flask import Blueprint, request, jsonify, current_app
from db import fetch_all, fetch_one, execute
from sqlalchemy import text

insumos_bp = Blueprint("insumos", __name__)

@insumos_bp.route("/api/insumos", methods=["GET"])
def get_insumos():
    try:
        s_id_filter = request.args.get("sucursal_id")
        is_global = not s_id_filter or s_id_filter == "global"

        where_clause = "" if is_global else "WHERE sucursal_id = :s_id"
        params = {} if is_global else {"s_id": s_id_filter}

        insumos = fetch_all(f"SELECT * FROM insumos {where_clause} ORDER BY nombre ASC", params)
        return jsonify(insumos), 200
    except Exception as e:
        current_app.logger.error(f"Error al obtener insumos: {e}")
        return jsonify({"error": "Error al obtener insumos"}), 500

@insumos_bp.route("/api/insumos", methods=["POST"])
def add_insumo():
    data = request.json
    try:
        params = {
            "nombre": data["nombre"].lower(),
            "stock": float(data.get("stock", 0)),
            "costo": float(data.get("costo_unidad", 0)),
            "unidad": data.get("unidad_medida", "unidad"),
            "sucursal_id": data.get("sucursal_id"),
            "porcion": data.get("porcion_estandar")
        }
        sql = "INSERT INTO insumos (nombre, stock, costo_unidad, unidad_medida, sucursal_id, porcion_estandar) VALUES (:nombre, :stock, :costo, :unidad, :sucursal_id, :porcion) RETURNING *"
        nuevo = fetch_one(sql, params)
        return jsonify(nuevo), 201
    except Exception as e:
        current_app.logger.error(f"Error al agregar insumo: {e}")
        return jsonify({"error": "Error al agregar insumo"}), 500

@insumos_bp.route("/api/insumos/<int:insumo_id>", methods=["PUT"])
def update_insumo(insumo_id):
    data = request.json
    try:
        sql = "UPDATE insumos SET stock = :stock, costo_unidad = :costo, unidad_medida = :unidad, nombre = :nombre, sucursal_id = :sucursal_id, porcion_estandar = :porcion, stock_minimo = :stock_minimo, alerta_vista = FALSE WHERE id = :id RETURNING *"
        params = {
            "id": insumo_id,
            "nombre": data["nombre"].lower(),
            "stock": data["stock"],
            "costo": data["costo_unidad"],
            "unidad": data["unidad_medida"],
            "sucursal_id": data.get("sucursal_id"),
            "porcion": data.get("porcion_estandar"),
            "stock_minimo": data.get("stock_minimo", 0)
        }
        actualizado = fetch_one(sql, params)
        if not actualizado:
            return jsonify({"error": "Insumo no encontrado"}), 404
        return jsonify(actualizado), 200
    except Exception as e:
        current_app.logger.error(f"Error al actualizar insumo: {e}")
        return jsonify({"error": "Error al actualizar insumo"}), 500

@insumos_bp.route("/api/insumos/<int:insumo_id>/alerta-vista", methods=["PUT"])
def marcar_alerta_vista(insumo_id):
    try:
        execute("UPDATE insumos SET alerta_vista = TRUE WHERE id = :id", {"id": insumo_id})
        return jsonify({"message": "Alerta marcada como vista"}), 200
    except Exception as e:
        current_app.logger.error(f"Error al marcar alerta: {e}")
        return jsonify({"error": "Error al marcar alerta"}), 500

@insumos_bp.route("/api/insumos/alertas", methods=["GET"])
def get_alertas_stock():
    """Obtener insumos con stock bajo (para carga inicial sin WebSocket)"""
    try:
        sql = """
            SELECT id, nombre, stock, stock_minimo, unidad_medida
            FROM insumos
            WHERE stock_minimo > 0
              AND stock <= stock_minimo
              AND alerta_vista = FALSE
            ORDER BY stock ASC
        """
        insumos_bajos = fetch_all(sql)
        alertas = []
        for insumo in insumos_bajos:
            stock = float(insumo["stock"] or 0)
            minimo = float(insumo["stock_minimo"] or 0)
            if stock <= 0:
                nivel = "critico"
            elif stock <= minimo * 0.5:
                nivel = "alto"
            else:
                nivel = "bajo"
            alertas.append({
                "id": insumo["id"],
                "nombre": insumo["nombre"],
                "stock": stock,
                "stock_minimo": minimo,
                "unidad_medida": insumo["unidad_medida"],
                "nivel": nivel
            })
        return jsonify(alertas), 200
    except Exception as e:
        current_app.logger.error(f"Error al obtener alertas: {e}")
        return jsonify({"error": "Error al obtener alertas"}), 500

@insumos_bp.route("/api/insumos/<int:insumo_id>", methods=["DELETE"])
def delete_insumo(insumo_id):
    try:
        # Primero eliminar de recetas si existe (o dejar que falle por FK)
        execute("DELETE FROM recetas WHERE insumo_id = :id", {"id": insumo_id})
        execute("DELETE FROM insumos WHERE id = :id", {"id": insumo_id})
        return jsonify({"message": "Insumo eliminado"}), 200
    except Exception as e:
        current_app.logger.error(f"Error al eliminar insumo: {e}")
        return jsonify({"error": "Error al eliminar insumo"}), 500
