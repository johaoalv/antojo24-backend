
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

        sql = f"SELECT id, fecha::text, monto, descripcion, sucursal_id, metodo_pago FROM inyecciones {where_clause} ORDER BY fecha DESC"
        results = fetch_all(sql, params)
        return jsonify(results), 200
    except Exception as e:
        current_app.logger.exception("Error en get_inyecciones: %s", e)
        return jsonify({"error": "Error al obtener inyecciones"}), 500

@inyecciones_bp.route("/api/inyecciones", methods=["POST"])
def add_inyeccion():
    from db import engine, text
    try:
        data = request.get_json()
        monto = data.get("monto")
        descripcion = data.get("descripcion", "")
        metodo_pago = data.get("metodo_pago", "efectivo")
        fecha = data.get("fecha") or date.today().isoformat()
        sucursal_id = data.get("sucursal_id")

        if not monto:
            return jsonify({"error": "Monto es requerido"}), 400

        with engine.begin() as conn:
            # 1. Insertar en tabla original (inyecciones)
            sql_iny = """
                INSERT INTO inyecciones (fecha, monto, descripcion, sucursal_id, metodo_pago)
                VALUES (:fecha, :monto, :descripcion, :sucursal_id, :metodo_pago)
                RETURNING id
            """
            res = conn.execute(text(sql_iny), {"fecha": fecha, "monto": monto, "descripcion": descripcion, "sucursal_id": sucursal_id, "metodo_pago": metodo_pago})
            iny_id = res.fetchone()[0]

            # 2. Insertar en movimientos_caja
            sql_mov = """
                INSERT INTO movimientos_caja (fecha, tipo, categoria, monto, descripcion, sucursal_id, referencia_id, metodo_pago)
                VALUES (:fecha, 'entrada', 'inversion', :monto, :descripcion, :sucursal_id, :referencia_id, :metodo_pago)
            """
            conn.execute(text(sql_mov), {
                "fecha": fecha,
                "monto": monto,
                "descripcion": descripcion,
                "sucursal_id": sucursal_id,
                "referencia_id": str(iny_id),
                "metodo_pago": metodo_pago
            })
        
        return jsonify({"msg": "Inyección de capital registrada en caja correctamente"}), 201
    except Exception as e:
        current_app.logger.exception("Error en add_inyeccion: %s", e)
        return jsonify({"error": "Error al registrar inyección"}), 500

@inyecciones_bp.route("/api/inyecciones/<int:iny_id>", methods=["DELETE"])
def delete_inyeccion(iny_id):
    from db import engine, text
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM inyecciones WHERE id = :id"), {"id": iny_id})
            conn.execute(text("DELETE FROM movimientos_caja WHERE referencia_id = :id AND tipo = 'entrada' AND categoria = 'inversion'"), {"id": str(iny_id)})
        return jsonify({"msg": "Inyección eliminada y movimiento de caja revertido"}), 200
    except Exception as e:
        current_app.logger.exception("Error en delete_inyeccion: %s", e)
        return jsonify({"error": "Error al eliminar inyección"}), 500
