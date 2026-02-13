
from flask import Blueprint, request, jsonify, current_app
from db import fetch_all, execute
from datetime import date

inversiones_bp = Blueprint("inversiones", __name__)

@inversiones_bp.route("/api/inversiones", methods=["GET"])
def get_inversiones():
    try:
        sql = "SELECT id, fecha::text, monto, descripcion FROM inversiones ORDER BY fecha DESC"
        results = fetch_all(sql)
        return jsonify(results), 200
    except Exception as e:
        current_app.logger.exception("Error en get_inversiones: %s", e)
        return jsonify({"error": "Error al obtener inversiones"}), 500

@inversiones_bp.route("/api/inversiones", methods=["POST"])
def add_inversion():
    try:
        data = request.get_json()
        monto = data.get("monto")
        descripcion = data.get("descripcion", "")
        fecha = data.get("fecha") or date.today().isoformat()

        if not monto:
            return jsonify({"error": "Monto es requerido"}), 400

        sql = "INSERT INTO inversiones (fecha, monto, descripcion) VALUES (:fecha, :monto, :descripcion)"
        execute(sql, {"fecha": fecha, "monto": monto, "descripcion": descripcion})
        
        return jsonify({"msg": "Inversión agregada correctamente"}), 201
    except Exception as e:
        current_app.logger.exception("Error en add_inversion: %s", e)
        return jsonify({"error": "Error al agregar inversión"}), 500

@inversiones_bp.route("/api/inversiones/<int:inv_id>", methods=["DELETE"])
def delete_inversion(inv_id):
    try:
        sql = "DELETE FROM inversiones WHERE id = :id"
        execute(sql, {"id": inv_id})
        return jsonify({"msg": "Inversión eliminada correctamente"}), 200
    except Exception as e:
        current_app.logger.exception("Error en delete_inversion: %s", e)
        return jsonify({"error": "Error al eliminar inversión"}), 500
