from flask import Blueprint, request, jsonify, current_app
from utils.emit_dashboard_update import emitir_dashboard_update
from db import engine
from sqlalchemy import text

pedido_bp = Blueprint("pedido", __name__)


@pedido_bp.route("/api/pedido", methods=["POST"])
def pedido():
    data = request.json
    current_app.logger.debug(f"Procesando pedido {data['pedido_id']}")
    
    try:
        with engine.begin() as conn:  # Esto inicia una transacción
            # 1. Insertar el pedido principal
            sql_pedido = """
                INSERT INTO pedidos (pedido_id, total_pedido, metodo_pago, sucursal_id, fecha)
                VALUES (:pedido_id, :total_pedido, :metodo_pago, :sucursal_id, :fecha)
            """
            conn.execute(text(sql_pedido), {
                "pedido_id": data["pedido_id"],
                "total_pedido": data["total_pedido"],
                "metodo_pago": data["metodo_pago"],
                "sucursal_id": data["sucursal_id"],
                "fecha": data["fecha"]
            })
            
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
            
        emitir_dashboard_update()
        return jsonify({"message": "Pedido insertado correctamente"}), 201
        
    except Exception as e:
        current_app.logger.error(f"Error al procesar pedido: {str(e)}")
        return jsonify({"error": "Error al procesar el pedido"}), 500


@pedido_bp.route("/api/pedido", methods=["OPTIONS"])
def handle_options():
    return '', 200
