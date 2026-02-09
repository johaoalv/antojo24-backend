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
        # Pre-validación de stock usando un diccionario para consolidar insumos
        insumos_requeridos = {}
        with engine.connect() as conn:
            for item in data.get("pedido", []):
                producto_nombre = item.get("producto", "").lower()
                try:
                    cantidad_vendida = int(float(item.get("cantidad", 0)))
                except (ValueError, TypeError):
                    cantidad_vendida = 0
                
                if cantidad_vendida <= 0:
                    continue

                sql_receta = """
                    SELECT i.id, i.nombre, i.stock, r.cantidad_requerida
                    FROM recetas r
                    JOIN insumos i ON r.insumo_id = i.id
                    WHERE LOWER(r.producto) = :producto
                """
                ingredientes = conn.execute(text(sql_receta), {"producto": producto_nombre}).mappings().all()
                for ing in ingredientes:
                    i_id = ing["id"]
                    if i_id not in insumos_requeridos:
                        insumos_requeridos[i_id] = {
                            "nombre": ing["nombre"],
                            "stock": float(ing["stock"] or 0),
                            "necesario": 0.0
                        }
                    insumos_requeridos[i_id]["necesario"] += float(ing["cantidad_requerida"] or 0) * cantidad_vendida

        # Verificar disponibilidad
        faltantes = []
        for info in insumos_requeridos.values():
            if info["stock"] < info["necesario"]:
                faltantes.append(f"{info['nombre']} (disponible: {info['stock']}, requerido: {info['necesario']})")
        
        if faltantes:
            current_app.logger.warning(f"⚠️ Stock insuficiente para el pedido: {faltantes}")
            return jsonify({
                "error": "Stock insuficiente",
                "detalles": "Faltan ingredientes: " + ", ".join(faltantes)
            }), 400

        # Procesar el pedido en una transacción
        with engine.begin() as conn:
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
                "monto_recibido": monto_recibido,
                "monto_vuelto": monto_vuelto
            }
            conn.execute(text(sql_pedido), params_pedido)
            
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
            
            # 3. Descontar stock (usando el cálculo previo)
            for i_id, info in insumos_requeridos.items():
                sql_update_stock = """
                    UPDATE insumos 
                    SET stock = stock - :cantidad_total
                    WHERE id = :insumo_id
                """
                conn.execute(text(sql_update_stock), {
                    "cantidad_total": info["necesario"],
                    "insumo_id": i_id
                })
            
            current_app.logger.info(f"✅ Pedido {data['pedido_id']} completado y stock actualizado.")
            
        current_app.logger.info("🚀 Emitiendo actualización de dashboard vía WebSocket...")
        emitir_dashboard_update()
        return jsonify(response_data), 201
        
    except Exception as e:
        current_app.logger.exception(f"Error al procesar pedido: {str(e)}")
        return jsonify({"error": "Error interno al procesar el pedido"}), 500


@pedido_bp.route("/api/pedido", methods=["OPTIONS"])
def handle_options():
    return '', 200
