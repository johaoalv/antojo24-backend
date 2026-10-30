from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
from db import fetch_all, engine
from sqlalchemy.exc import OperationalError
from uuid import UUID
from utils.tesoreria import (dinero, saldos_operativos, historial_traspasos,
                             registrar_traspaso, SaldoCambio)

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

        dia = datetime.strptime(fecha, '%Y-%m-%d')
        inicio = dia.isoformat()
        fin = (dia + timedelta(days=1)).isoformat()
        with engine.connect() as conn:
            saldos = saldos_operativos(conn, sucursal_id, dia)
        saldo_inicial_yappy = float(saldos['yappy'])
        saldo_inicial_efectivo = float(saldos['efectivo'])

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
            WHERE sucursal_id = :s AND fecha >= :inicio AND fecha < :fin
            ORDER BY fecha ASC, id ASC
        """
        rows = fetch_all(sql, {"s": sucursal_id, "inicio": inicio, "fin": fin})

        return jsonify({
            "fecha": fecha,
            "saldo_inicial_yappy": round(saldo_inicial_yappy, 2),
            "saldo_inicial_efectivo": round(saldo_inicial_efectivo, 2),
            "movimientos": rows
        }), 200

    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        current_app.logger.exception("Error en get_libro_caja: %s", e)
        return jsonify({"error": "Error interno"}), 500


@finanzas_bp.route('/api/finanzas/traspasos', methods=['GET'])
def get_traspasos():
    sucursal = request.args.get('sucursal_id')
    with engine.connect() as conn:
        rows = historial_traspasos(conn, None if sucursal == 'global' else sucursal)
    return jsonify(rows)


@finanzas_bp.route('/api/finanzas/traspasos', methods=['POST'])
def post_traspaso():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError('Traspaso inválido')
        sucursal = data.get('sucursal_id')
        if not isinstance(sucursal, str) or not sucursal.strip() or sucursal == 'global':
            raise ValueError('Selecciona una sucursal para traspasar')
        try:
            identificador = str(UUID(str(data.get('id'))))
            conservar = {m: dinero(data['conservar'][m]) for m in ('yappy','efectivo')}
            esperados = {m: dinero(data['saldos_esperados'][m]) for m in ('yappy','efectivo')}
        except (KeyError, TypeError, AttributeError):
            raise ValueError('Indica los saldos actuales y los montos a conservar') from None
        with engine.begin() as conn:
            creado = registrar_traspaso(conn, identificador, sucursal, conservar, esperados)
        # La confirmación ya fue guardada; una notificación no debe convertirla en error.
        from socket_instance import socketio
        try:
            socketio.emit('dashboard_update', {'sucursal_id': sucursal})
        except Exception:
            current_app.logger.exception('No se pudo notificar el traspaso')
        return jsonify({'id': identificador, 'message': 'Traspaso registrado', 'creado': creado}), 201 if creado else 200
    except SaldoCambio as e:
        return jsonify(error=str(e)), 409
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except OperationalError:
        current_app.logger.exception('Conflicto al registrar traspaso')
        return jsonify(error='La caja está ocupada. Reintenta el traspaso.'), 409
    except Exception:
        current_app.logger.exception('Error al registrar traspaso')
        return jsonify(error='No se pudo registrar el traspaso'), 500
