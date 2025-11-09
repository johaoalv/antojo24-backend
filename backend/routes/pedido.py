from flask import Blueprint, request, jsonify, current_app
from utils.emit_dashboard_update import emitir_dashboard_update
from db import engine
from sqlalchemy import text

pedido_bp = Blueprint("pedido", __name__)


@pedido_bp.route("/api/pedido", methods=["POST"])
def pedido():
    data = request.json
    current_app.logger.debug(f"Procesando pedido {data['pedido_id']}")

    # --- Nueva lógica para pagos en efectivo ---
    monto_recibido = None
    monto_vuelto = None
    response_data = {"message": "Pedido insertado correctamente"}

    if data.get("metodo_pago") == "efectivo":
        try:
            monto_recibido = float(data.get("monto_recibido", 0))
            total_pedido = float(data.get("total_pedido", 0))
            monto_vuelto = monto_recibido - total_pedido

            current_app.logger.info(f"💵 Pago en efectivo detectado.")
            current_app.logger.info(f"   - Monto recibido: {monto_recibido:.2f}")
            current_app.logger.info(f"   - Total pedido:   {total_pedido:.2f}")
            current_app.logger.info(f"   - Vuelto a dar:   {monto_vuelto:.2f}")

            response_data["monto_vuelto"] = round(monto_vuelto, 2)

        except (ValueError, TypeError) as e:
            current_app.logger.error(f"Error al calcular el vuelto: {e}")
            return jsonify({"error": "Datos de monto inválidos para pago en efectivo"}), 400

    try:
        with engine.begin() as conn:  # Esto inicia una transacción
            # 1. Insertar el pedido principal
            sql_pedido = """
                INSERT INTO pedidos (pedido_id, total_pedido, metodo_pago, sucursal_id, fecha, monto_recibido, monto_vuelto)
                VALUES (:pedido_id, :total_pedido, :metodo_pago, :sucursal_id, :fecha, :monto_recibido, :monto_vuelto)
            """
            params_pedido = {
                "pedido_id": data["pedido_id"],
                "total_pedido": data["total_pedido"],
                "metodo_pago": data["metodo_pago"],
                "sucursal_id": data["sucursal_id"],
                "fecha": data["fecha"],
                "monto_recibido": monto_recibido, # Será None si no es efectivo
                "monto_vuelto": monto_vuelto      # Será None si no es efectivo
            }
            
            current_app.logger.debug(f"Insertando en 'pedidos' con params: {params_pedido}")
            conn.execute(text(sql_pedido), params_pedido)
            
            current_app.logger.debug("Pedido principal insertado")
            
            # 2. Insertar los productos del pedido
            sql_productos = """
                INSERT INTO productos_pedido (pedido_id, producto, cantidad, total_item, total_pedido, metodo_pago, sucursal_id, fecha)
                VALUES (:pedido_id, :producto, :cantidad, :total_item, :total_pedido, :metodo_pago, :sucursal_id, :fecha)
            """
            
            for item in data["pedido"]:
                conn.execute(text(sql_productos), {
                    "pedido_id": data["pedido_id"],
                    "producto": item["producto"],
                    "cantidad": item["cantidad"],
                    "total_item": item["total_item"],
                    "total_pedido": data["total_pedido"],
                    "metodo_pago": data["metodo_pago"],
                    "sucursal_id": data["sucursal_id"],
                    "fecha": data["fecha"]
                })
            
            current_app.logger.debug("Productos insertados")
            # La transacción se confirma automáticamente si llegamos aquí
            
        current_app.logger.info("🚀 Emitiendo actualización de dashboard vía WebSocket...")
        emitir_dashboard_update()
        return jsonify(response_data), 201
        
    except Exception as e:
        current_app.logger.error(f"Error al procesar pedido: {str(e)}")
        return jsonify({"error": "Error al procesar el pedido"}), 500


@pedido_bp.route("/api/pedido", methods=["OPTIONS"])
def handle_options():
    return '', 200
