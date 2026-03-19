
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
    from db import engine, text
    try:
        data = request.get_json()
        monto = data.get("monto")
        descripcion = data.get("descripcion", "")
        categoria = data.get("categoria", "operativo")
        fecha = data.get("fecha") or date.today().isoformat()
        sucursal_id = data.get("sucursal_id")

        if not monto:
            return jsonify({"error": "Monto es requerido"}), 400

        # Regla de Oro: Autosignar categoría 'inventario' si es Jumbo o Sysco
        desc_lower = descripcion.lower()
        if "jumbo" in desc_lower or "sysco" in desc_lower:
            categoria = "inventario"

        with engine.begin() as conn:
            # 1. Insertar en tabla original (gastos)
            sql_gasto = """
                INSERT INTO gastos (fecha, monto, descripcion, sucursal_id, categoria) 
                VALUES (:fecha, :monto, :descripcion, :sucursal_id, :categoria)
                RETURNING id
            """
            res = conn.execute(text(sql_gasto), {"fecha": fecha, "monto": monto, "descripcion": descripcion, "sucursal_id": sucursal_id, "categoria": categoria})
            g_id = res.fetchone()[0]

            # 2. Insertar en movimientos_caja
            sql_mov = """
                INSERT INTO movimientos_caja (fecha, tipo, categoria, monto, descripcion, sucursal_id, referencia_id)
                VALUES (:fecha, 'salida', :categoria, :monto, :descripcion, :sucursal_id, :referencia_id)
            """
            conn.execute(text(sql_mov), {
                "fecha": fecha,
                "categoria": categoria,
                "monto": monto,
                "descripcion": descripcion,
                "sucursal_id": sucursal_id,
                "referencia_id": str(g_id)
            })
        
        return jsonify({"msg": "Gasto agregado y registrado en caja correctamente"}), 201
    except Exception as e:
        current_app.logger.exception("Error en add_gasto: %s", e)
        return jsonify({"error": "Error al agregar gasto"}), 500

@gastos_bp.route("/api/gastos/<int:g_id>", methods=["DELETE"])
def delete_gasto(g_id):
    from db import engine, text
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM gastos WHERE id = :id"), {"id": g_id})
            conn.execute(text("DELETE FROM movimientos_caja WHERE referencia_id = :id AND tipo = 'salida'"), {"id": str(g_id)})
        return jsonify({"msg": "Gasto eliminado y movimiento de caja revertido"}), 200
    except Exception as e:
        current_app.logger.exception("Error en delete_gasto: %s", e)
        return jsonify({"error": "Error al eliminar gasto"}), 500
