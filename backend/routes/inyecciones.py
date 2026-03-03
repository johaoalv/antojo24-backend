
from flask import Blueprint, request, jsonify, current_app
from db import fetch_all, execute
from datetime import date

inyecciones_bp = Blueprint("inyecciones", __name__)

@inyecciones_bp.route("/api/inyecciones", methods=["GET"])
def get_inyecciones():
    try:
        s_id_filter = request.args.get("sucursal_id")
        is_global = not s_id_filter or s_id_filter == "global"

        where_clause = "" if is_global else "WHERE sucursal_id = :s_id"
        params = {} if is_global else {"s_id": s_id_filter}

        sql = f"SELECT id, fecha::text, monto, descripcion, sucursal_id FROM inyecciones {where_clause} ORDER BY fecha DESC"
        results = fetch_all(sql, params)
        return jsonify(results), 200
    except Exception as e:
        current_app.logger.exception("Error en get_inyecciones: %s", e)
        return jsonify({"error": "Error al obtener inyecciones"}), 500

@inyecciones_bp.route("/api/inyecciones", methods=["POST"])
def add_inyeccion():
    try:
        data = request.get_json()
        monto = data.get("monto")
        descripcion = data.get("descripcion", "")
        fecha = data.get("fecha") or date.today().isoformat()
        sucursal_id = data.get("sucursal_id")

        if not monto:
            return jsonify({"error": "Monto es requerido"}), 400

        sql = "INSERT INTO inyecciones (fecha, monto, descripcion, sucursal_id) VALUES (:fecha, :monto, :descripcion, :sucursal_id)"
        execute(sql, {"fecha": fecha, "monto": monto, "descripcion": descripcion, "sucursal_id": sucursal_id})
        
        return jsonify({"msg": "Inyección de capital registrada correctamente"}), 201
    except Exception as e:
        current_app.logger.exception("Error en add_inyeccion: %s", e)
        return jsonify({"error": "Error al registrar inyección"}), 500

@inyecciones_bp.route("/api/inyecciones/<int:iny_id>", methods=["DELETE"])
def delete_inyeccion(iny_id):
    try:
        sql = "DELETE FROM inyecciones WHERE id = :id"
        execute(sql, {"id": iny_id})
        return jsonify({"msg": "Inyección eliminada correctamente"}), 200
    except Exception as e:
        current_app.logger.exception("Error en delete_inyeccion: %s", e)
        return jsonify({"error": "Error al eliminar inyección"}), 500
