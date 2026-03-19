from flask import Blueprint, jsonify, request, current_app
from db import fetch_all

finanzas_bp = Blueprint("finanzas", __name__)

@finanzas_bp.route("/api/finanzas/movimientos", methods=["GET"])
def get_movimientos():
    try:
        s_id_filter = request.args.get("sucursal_id")
        is_global = not s_id_filter or s_id_filter == "global"

        where_clause = "" if is_global else "WHERE sucursal_id = :s_id"
        params = {} if is_global else {"s_id": s_id_filter}

        sql = f"""
            SELECT id, fecha::text, tipo, categoria, monto, descripcion, sucursal_id 
            FROM movimientos_caja 
            {where_clause} 
            ORDER BY fecha DESC
        """
        results = fetch_all(sql, params)
        return jsonify(results), 200
    except Exception as e:
        current_app.logger.exception("Error en get_movimientos: %s", e)
        return jsonify({"error": "Error al obtener movimientos de caja"}), 500
