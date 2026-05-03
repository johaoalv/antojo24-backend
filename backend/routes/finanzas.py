from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
from db import fetch_all

finanzas_bp = Blueprint("finanzas", __name__)


def get_panama_date():
    return (datetime.utcnow() - timedelta(hours=5)).strftime("%Y-%m-%d")


@finanzas_bp.route("/api/finanzas/movimientos", methods=["GET"])
def get_movimientos():
    try:
        s_id_filter = request.args.get("sucursal_id")
        is_global = not s_id_filter or s_id_filter == "global"

        where_clause = "" if is_global else "WHERE sucursal_id = :s_id"
        params = {} if is_global else {"s_id": s_id_filter}

        sql = f"""
            SELECT id, fecha::text, tipo, categoria, monto, descripcion, sucursal_id, metodo_pago
            FROM movimientos_caja
            {where_clause}
            ORDER BY fecha DESC
        """
        results = fetch_all(sql, params)
        return jsonify(results), 200
    except Exception as e:
        current_app.logger.exception("Error en get_movimientos: %s", e)
        return jsonify({"error": "Error al obtener movimientos de caja"}), 500


@finanzas_bp.route("/api/finanzas/pedido-detalle/<pedido_id>", methods=["GET"])
def get_pedido_detalle(pedido_id):
    try:
        rows = fetch_all(
            "SELECT producto, cantidad, total_item, metodo_pago FROM productos_pedido WHERE pedido_id = :pid ORDER BY producto ASC",
            {"pid": pedido_id}
        )
        return jsonify(rows), 200
    except Exception as e:
        current_app.logger.exception("Error en get_pedido_detalle: %s", e)
        return jsonify({"error": "Error interno"}), 500


@finanzas_bp.route("/api/finanzas/libro-caja", methods=["GET"])
def get_libro_caja():
    try:
        sucursal_id = request.args.get("sucursal_id")
        fecha = request.args.get("fecha", get_panama_date())

        if not sucursal_id or sucursal_id == "global":
            return jsonify({"error": "sucursal_id requerido"}), 400

        inicio = f"{fecha}T00:00:00"
        fin = f"{fecha}T23:59:59"
        inicio_mes = f"{fecha[:7]}-01T00:00:00"

        # Saldo inicial del día: $50/$50 si es el 1ro del mes,
        # si no, lo acumulado desde el 1ro hasta antes de este día
        if inicio == inicio_mes:
            saldo_inicial_yappy = 50.0
            saldo_inicial_efectivo = 50.0
        else:
            flujo_previo = fetch_all("""
                SELECT metodo_pago,
                       SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) as saldo
                FROM movimientos_caja
                WHERE sucursal_id = :s AND fecha >= :inicio_mes AND fecha < :inicio_dia
                GROUP BY metodo_pago
            """, {"s": sucursal_id, "inicio_mes": inicio_mes, "inicio_dia": inicio})
            flujo_map = {r["metodo_pago"]: float(r["saldo"] or 0) for r in flujo_previo}
            saldo_inicial_yappy = 50.0 + flujo_map.get("yappy", 0)
            saldo_inicial_efectivo = 50.0 + flujo_map.get("efectivo", 0)

        sql = """
            SELECT
                id,
                fecha::text as fecha,
                tipo,
                categoria,
                monto,
                descripcion,
                metodo_pago,
                referencia_id
            FROM movimientos_caja
            WHERE sucursal_id = :s AND fecha >= :inicio AND fecha <= :fin
            ORDER BY fecha ASC
        """
        rows = fetch_all(sql, {"s": sucursal_id, "inicio": inicio, "fin": fin})

        return jsonify({
            "fecha": fecha,
            "saldo_inicial_yappy": round(saldo_inicial_yappy, 2),
            "saldo_inicial_efectivo": round(saldo_inicial_efectivo, 2),
            "movimientos": rows
        }), 200

    except Exception as e:
        current_app.logger.exception("Error en get_libro_caja: %s", e)
        return jsonify({"error": "Error interno"}), 500
