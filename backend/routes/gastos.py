
from flask import Blueprint, request, jsonify, current_app
from db import fetch_all, execute
from datetime import date

gastos_bp = Blueprint("gastos", __name__)

@gastos_bp.route("/api/gastos", methods=["GET"])
def get_gastos():
    try:
        s_id_filter = request.args.get("sucursal_id")
        is_global = not s_id_filter or s_id_filter == "global"

        where_clause = "" if is_global else "WHERE sucursal_id = :s_id"
        params = {} if is_global else {"s_id": s_id_filter}

        sql = f"SELECT id, fecha::text, monto, descripcion, sucursal_id, categoria FROM gastos {where_clause} ORDER BY fecha DESC"
        results = fetch_all(sql, params)
        return jsonify(results), 200
    except Exception as e:
        current_app.logger.exception("Error en get_gastos: %s", e)
        return jsonify({"error": "Error al obtener gastos"}), 500

@gastos_bp.route("/api/gastos", methods=["POST"])
def add_gasto():
    try:
        data = request.get_json()
        monto = data.get("monto")
        descripcion = data.get("descripcion", "")
        categoria = data.get("categoria", "operativo")
        fecha = data.get("fecha") or date.today().isoformat()
        sucursal_id = data.get("sucursal_id") # Opcional, puede ser central/global

        if not monto:
            return jsonify({"error": "Monto es requerido"}), 400

        sql = "INSERT INTO gastos (fecha, monto, descripcion, sucursal_id, categoria) VALUES (:fecha, :monto, :descripcion, :sucursal_id, :categoria)"
        execute(sql, {"fecha": fecha, "monto": monto, "descripcion": descripcion, "sucursal_id": sucursal_id, "categoria": categoria})
        
        return jsonify({"msg": "Gasto agregado correctamente"}), 201
    except Exception as e:
        current_app.logger.exception("Error en add_gasto: %s", e)
        return jsonify({"error": "Error al agregar gasto"}), 500

@gastos_bp.route("/api/gastos/<int:g_id>", methods=["DELETE"])
def delete_gasto(g_id):
    try:
        sql = "DELETE FROM gastos WHERE id = :id"
        execute(sql, {"id": g_id})
        return jsonify({"msg": "Gasto eliminado correctamente"}), 200
    except Exception as e:
        current_app.logger.exception("Error en delete_gasto: %s", e)
        return jsonify({"error": "Error al eliminar gasto"}), 500
