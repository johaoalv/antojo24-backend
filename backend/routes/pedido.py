from flask import Blueprint, request, jsonify, current_app
from utils.emit_dashboard_update import emitir_dashboard_update
from utils.emit_stock_alerts import emitir_stock_alerts
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

                # DESCOMPONER COMBOS EN PRODUCTOS BASE
                sql_prod = "SELECT es_combo, combo_items FROM productos WHERE LOWER(nombre) = :producto"
                prod = conn.execute(text(sql_prod), {"producto": producto_nombre}).mappings().first()

                productos_a_procesar = []
                if prod and prod["es_combo"]:
                    import json
                    try:
                        # Obtener combo_items de la BD
                        if prod["combo_items"]:
                            items_combo = prod["combo_items"] if isinstance(prod["combo_items"], list) else json.loads(prod["combo_items"])
                        else:
                            items_combo = []

                        for ci in items_combo:
                            # Procesar items fijos del combo
                            base_prod = conn.execute(text("SELECT nombre FROM productos WHERE id = :id"), {"id": ci["id"]}).mappings().first()
                            if base_prod:
                                productos_a_procesar.append({
                                    "nombre": base_prod["nombre"].lower(),
                                    "cantidad": float(ci.get("cantidad", 1)) * cantidad_vendida
                                })
                    except Exception as e:
                        current_app.logger.error(f"Error procesando combo_items: {e}")
                else:
                    # Si no es combo, lo procesamos como siempre
                    productos_a_procesar.append({
                        "nombre": producto_nombre,
                        "cantidad": cantidad_vendida
                    })

                # Ahora iterar sobre productos_a_procesar para buscar sus recetas
                for bp in productos_a_procesar:
                    sql_receta = """
                        SELECT i.id, i.nombre, i.stock, i.costo_unidad, r.cantidad_requerida
                        FROM recetas r
                        JOIN insumos i ON r.insumo_id = i.id
                        WHERE LOWER(r.producto) = :producto
                    """
                    ingredientes = conn.execute(text(sql_receta), {"producto": bp["nombre"]}).mappings().all()

                    # Calcular costo del producto individual (unitario)
                    costo_producto_unitario = 0.0
                    for ing in ingredientes:
                        costo_ing = float(ing["costo_unidad"] or 0) * float(ing["cantidad_requerida"] or 0)
                        costo_producto_unitario += costo_ing

                        i_id = ing["id"]
                        if i_id not in insumos_requeridos:
                            insumos_requeridos[i_id] = {
                                "nombre": ing["nombre"],
                                "stock": float(ing["stock"] or 0),
                                "necesario": 0.0
                            }
                        insumos_requeridos[i_id]["necesario"] += float(ing["cantidad_requerida"] or 0) * bp["cantidad"]

                    # Guardar el costo unitario calculado para este producto/item en el pedido
                    # Lo vinculamos al item original de data["pedido"] si es posible
                    # (Más simple: lo calculamos de nuevo al insertar cada item)

        # --- BOLSAS DE ENTREGA (manual desde POS) ---
        bolsas = int(data.get("bolsas", 0))
        if bolsas > 0:
            with engine.connect() as conn:
                sql_bolsa = "SELECT id, nombre, stock, costo_unidad FROM insumos WHERE id = 30"
                bolsa = conn.execute(text(sql_bolsa)).mappings().first()
                if bolsa:
                    bolsa_id = bolsa["id"]
                    if bolsa_id not in insumos_requeridos:
                        insumos_requeridos[bolsa_id] = {
                            "nombre": bolsa["nombre"],
                            "stock": float(bolsa["stock"] or 0),
                            "necesario": 0.0
                        }
                    insumos_requeridos[bolsa_id]["necesario"] += float(bolsas)
                    current_app.logger.info(f"🛍️ {bolsas} bolsa(s) agregada(s) al pedido {data['pedido_id']}")

        # Calcular el costo total de TODO el pedido
        # (Sumando todos los insumos multiplicados por su costo unitario en el inventario actual)
        costo_total_pedido = 0.0
        with engine.connect() as conn:
            for i_id, info in insumos_requeridos.items():
                sql_costo_insumo = "SELECT costo_unidad FROM insumos WHERE id = :id"
                ci = conn.execute(text(sql_costo_insumo), {"id": i_id}).mappings().first()
                if ci:
                    costo_total_pedido += (float(ci["costo_unidad"] or 0) * info["necesario"])

        # Procesar el pedido en una transacción
        with engine.begin() as conn:
            # 1. Insertar el pedido principal con costo_total
            sql_pedido = """
                INSERT INTO pedidos (pedido_id, total_pedido, metodo_pago, sucursal_id, fecha, monto_recibido, monto_vuelto, costo_total, tipo_pedido, estado_pago)
                VALUES (:pedido_id, :total_pedido, :metodo_pago, :sucursal_id, :fecha, :monto_recibido, :monto_vuelto, :costo_total, :tipo_pedido, :estado_pago)
            """
            params_pedido = {
                "pedido_id": data["pedido_id"],
                "total_pedido": data["total_pedido"],
                "metodo_pago": data["metodo_pago"],
                "sucursal_id": data["sucursal_id"],
                "fecha": data["fecha"],
                "monto_recibido": monto_recibido,
                "monto_vuelto": monto_vuelto,
                "costo_total": costo_total_pedido,
                "tipo_pedido": data.get("tipo_pedido", "local"),
                "estado_pago": data.get("estado_pago", "pagado")
            }
            conn.execute(text(sql_pedido), params_pedido)
            
            # 2. Insertar los productos del pedido en la tabla oficial productos_pedido
            sql_productos = """
                INSERT INTO productos_pedido (pedido_id, producto, cantidad, total_item, metodo_pago, sucursal_id, fecha, costo_unitario, producto_id)
                VALUES (:pedido_id, :producto, :cantidad, :total_item, :metodo_pago, :sucursal_id, :fecha, :costo_unitario, :producto_id)
            """
            
            for item in data["pedido"]:
                # Obtener producto_id
                item_name = item["producto"].lower()
                sql_get_producto = "SELECT id FROM productos WHERE LOWER(nombre) = :producto"
                prod_res = conn.execute(text(sql_get_producto), {"producto": item_name}).mappings().first()
                p_id = prod_res["id"] if prod_res else None

                # Calcular costo unitario (frozen) para este producto específico
                sql_get_costo = """
                    SELECT SUM(r.cantidad_requerida * i.costo_unidad) as costo_total
                    FROM recetas r
                    JOIN insumos i ON r.insumo_id = i.id
                    WHERE LOWER(r.producto) = :producto
                """
                res_costo = conn.execute(text(sql_get_costo), {"producto": item_name}).mappings().first()
                costo_u = float(res_costo["costo_total"] or 0) if res_costo else 0.0

                conn.execute(text(sql_productos), {
                    "pedido_id": data["pedido_id"],
                    "producto": item["producto"],
                    "cantidad": item["cantidad"],
                    "total_item": item["total_item"],
                    "metodo_pago": data["metodo_pago"],
                    "sucursal_id": data["sucursal_id"],
                    "fecha": data["fecha"],
                    "costo_unitario": costo_u,
                    "producto_id": p_id
                })
            
            # 3. Registrar el MOVIMIENTO DE CAJA (Solo si el pago ya fue recibido)
            estado_pago = data.get("estado_pago", "pagado")
            if estado_pago != "pendiente":
                sql_movimiento = """
                    INSERT INTO movimientos_caja (fecha, tipo, categoria, monto, descripcion, sucursal_id, referencia_id, metodo_pago)
                    VALUES (:fecha, 'entrada', 'venta', :monto, :descripcion, :sucursal_id, :referencia_id, :metodo_pago)
                """
                conn.execute(text(sql_movimiento), {
                    "fecha": data["fecha"],
                    "monto": data["total_pedido"],
                    "descripcion": f"Venta registrada - ID: {data['pedido_id']}",
                    "sucursal_id": data["sucursal_id"],
                    "referencia_id": data["pedido_id"],
                    "metodo_pago": data["metodo_pago"]
                })
            else:
                current_app.logger.info(f"⏳ Pedido {data['pedido_id']} pendiente de pago (delivery). Movimiento de caja diferido.")
            
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
        emitir_stock_alerts()
        return jsonify(response_data), 201
        
    except Exception as e:
        current_app.logger.exception(f"Error al procesar pedido: {str(e)}")
        return jsonify({"error": "Error interno al procesar el pedido"}), 500


@pedido_bp.route("/api/pedido/<pedido_id>", methods=["DELETE"])
def eliminar_pedido(pedido_id):
    current_app.logger.info(f"🗑️ Solicitud para eliminar pedido: {pedido_id}")
    try:
        restored_items = []
        with engine.begin() as conn:
            # 1. Obtener los productos del pedido para saber qué devolver al inventario
            sql_productos = "SELECT producto, cantidad FROM productos_pedido WHERE pedido_id = :pedido_id"
            items = conn.execute(text(sql_productos), {"pedido_id": pedido_id}).mappings().all()

            if not items:
                # Si no hay productos en productos_pedido, verificamos si existe en pedidos
                sql_check = "SELECT 1 FROM pedidos WHERE pedido_id = :pedido_id"
                exists = conn.execute(text(sql_check), {"pedido_id": pedido_id}).first()
                if not exists:
                    return jsonify({"error": "Pedido no encontrado"}), 404

            # 2. Revertir el stock para cada producto
            for item in items:
                producto_nombre = item["producto"].lower()
                cantidad_vendida = float(item["cantidad"])

                # Obtener si el producto es combo
                sql_prod = "SELECT es_combo, combo_items FROM productos WHERE LOWER(nombre) = :producto"
                prod = conn.execute(text(sql_prod), {"producto": producto_nombre}).mappings().first()

                productos_a_procesar = []
                if prod and prod["es_combo"] and prod["combo_items"]:
                    import json
                    try:
                        items_combo = prod["combo_items"] if isinstance(prod["combo_items"], list) else json.loads(prod["combo_items"])
                        for ci in items_combo:
                            base_prod = conn.execute(text("SELECT nombre FROM productos WHERE id = :id"), {"id": ci["id"]}).mappings().first()
                            if base_prod:
                                productos_a_procesar.append({
                                    "nombre": base_prod["nombre"].lower(),
                                    "cantidad": float(ci.get("cantidad", 1)) * cantidad_vendida
                                })
                    except Exception as e:
                        current_app.logger.error(f"Error procesando combo_items en eliminación: {e}")
                else:
                    productos_a_procesar.append({
                        "nombre": producto_nombre,
                        "cantidad": cantidad_vendida
                    })

                for bp in productos_a_procesar:
                    # Obtener la receta para este producto con el nombre del insumo
                    sql_receta = """
                        SELECT r.insumo_id, i.nombre as insumo_nombre, r.cantidad_requerida
                        FROM recetas r
                        JOIN insumos i ON r.insumo_id = i.id
                        WHERE LOWER(r.producto) = :producto
                    """
                    ingredientes = conn.execute(text(sql_receta), {"producto": bp["nombre"]}).mappings().all()

                    for ing in ingredientes:
                        total_a_devolver = float(ing["cantidad_requerida"]) * bp["cantidad"]
                        
                        sql_update_stock = """
                            UPDATE insumos 
                            SET stock = stock + :cantidad
                            WHERE id = :insumo_id
                        """
                        conn.execute(text(sql_update_stock), {
                            "cantidad": total_a_devolver,
                            "insumo_id": ing["insumo_id"]
                        })
                        
                        restored_items.append({
                            "insumo": ing["insumo_nombre"],
                            "cantidad": total_a_devolver,
                            "producto": bp["nombre"]
                        })
                        current_app.logger.debug(f"Restaurado {total_a_devolver} del insumo {ing['insumo_nombre']} por {bp['nombre']}")

            # 3. Eliminar registros de las tablas
            conn.execute(text("DELETE FROM productos_pedido WHERE pedido_id = :pedido_id"), {"pedido_id": pedido_id})
            conn.execute(text("DELETE FROM pedidos WHERE pedido_id = :pedido_id"), {"pedido_id": pedido_id})
            conn.execute(text("DELETE FROM movimientos_caja WHERE referencia_id = :pedido_id AND categoria = 'venta'"), {"pedido_id": pedido_id})

            current_app.logger.info(f"✅ Pedido {pedido_id} eliminado, stock restaurado y movimiento de caja revertido.")

        emitir_dashboard_update()
        emitir_stock_alerts()
        return jsonify({
            "message": "Pedido eliminado y stock restaurado correctamente",
            "restored_items": restored_items
        }), 200

    except Exception as e:
        current_app.logger.exception(f"Error al eliminar pedido {pedido_id}: {str(e)}")
        return jsonify({"error": "Error interno al eliminar el pedido"}), 500


@pedido_bp.route("/api/pedido/<pedido_id>/pagar", methods=["PATCH"])
def marcar_pagado(pedido_id):
    """Marca un pedido pendiente como pagado y crea el movimiento de caja."""
    current_app.logger.info(f"💰 Marcando pedido {pedido_id} como pagado...")
    try:
        body = request.get_json(silent=True) or {}
        monto_custom = body.get("monto")

        with engine.begin() as conn:
            # 1. Verificar que el pedido existe y está pendiente
            sql_check = "SELECT pedido_id, total_pedido, fecha, sucursal_id, estado_pago, metodo_pago FROM pedidos WHERE pedido_id = :pid"
            pedido = conn.execute(text(sql_check), {"pid": pedido_id}).mappings().first()

            if not pedido:
                return jsonify({"error": "Pedido no encontrado"}), 404

            if pedido["estado_pago"] == "pagado":
                return jsonify({"error": "Este pedido ya está marcado como pagado"}), 409

            monto_final = float(monto_custom) if monto_custom is not None else float(pedido["total_pedido"])

            # 2. Actualizar estado_pago
            conn.execute(text("UPDATE pedidos SET estado_pago = 'pagado' WHERE pedido_id = :pid"), {"pid": pedido_id})

            # 3. Crear el movimiento de caja que se difirió
            sql_mov = """
                INSERT INTO movimientos_caja (fecha, tipo, categoria, monto, descripcion, sucursal_id, referencia_id, metodo_pago)
                VALUES (:fecha, 'entrada', 'venta', :monto, :descripcion, :sucursal_id, :referencia_id, :metodo_pago)
            """
            conn.execute(text(sql_mov), {
                "fecha": str(pedido["fecha"]),
                "monto": monto_final,
                "descripcion": f"Pago recibido (delivery) - ID: {pedido_id}",
                "sucursal_id": pedido["sucursal_id"],
                "referencia_id": pedido_id,
                "metodo_pago": pedido["metodo_pago"]
            })

            current_app.logger.info(f"✅ Pedido {pedido_id} marcado como pagado. Movimiento de caja creado.")

        emitir_dashboard_update()
        return jsonify({"message": "Pedido marcado como pagado y movimiento de caja registrado"}), 200

    except Exception as e:
        current_app.logger.exception(f"Error al marcar pedido como pagado: {str(e)}")
        return jsonify({"error": "Error interno al procesar el pago"}), 500


@pedido_bp.route("/api/pedidos/liquidacion-pedidosya", methods=["POST"])
def liquidacion_pedidosya():
    """Marca pedidos PedidosYa como pagados y registra el monto neto depositado."""
    try:
        body        = request.get_json()
        pedido_ids  = body.get("pedidos", [])
        monto_dep   = float(body.get("monto_depositado", 0))
        sucursal_id = body.get("sucursal_id")

        if not pedido_ids or monto_dep <= 0:
            return jsonify({"error": "Pedidos y monto depositado son requeridos"}), 400

        pagados = 0
        with engine.begin() as conn:
            for pid in pedido_ids:
                pedido = conn.execute(text("SELECT estado_pago FROM pedidos WHERE pedido_id = :pid"), {"pid": pid}).mappings().first()
                if not pedido or pedido["estado_pago"] == "pagado":
                    continue
                conn.execute(text("UPDATE pedidos SET estado_pago = 'pagado' WHERE pedido_id = :pid"), {"pid": pid})
                pagados += 1

            conn.execute(text("""
                INSERT INTO movimientos_caja (fecha, tipo, categoria, monto, descripcion, sucursal_id, metodo_pago)
                VALUES (NOW() AT TIME ZONE 'America/Panama', 'entrada', 'venta', :monto,
                        'Liquidacion PedidosYa - ' || :n || ' pedidos', :sucursal_id, 'yappy')
            """), {"monto": monto_dep, "n": pagados, "sucursal_id": sucursal_id})

        emitir_dashboard_update()
        return jsonify({"pagados": pagados, "monto": monto_dep}), 200

    except Exception as e:
        current_app.logger.exception(f"Error en liquidacion_pedidosya: {str(e)}")
        return jsonify({"error": "Error interno al procesar la liquidacion"}), 500


@pedido_bp.route("/api/pedidos/liquidacion-uber", methods=["POST"])
def liquidacion_uber():
    """Marca pedidos Uber como pagados y registra el monto neto depositado."""
    try:
        body        = request.get_json()
        pedido_ids  = body.get("pedidos", [])
        monto_dep   = float(body.get("monto_depositado", 0))
        sucursal_id = body.get("sucursal_id")

        if not pedido_ids or monto_dep <= 0:
            return jsonify({"error": "Pedidos y monto depositado son requeridos"}), 400

        pagados = 0
        with engine.begin() as conn:
            for pid in pedido_ids:
                pedido = conn.execute(text("SELECT estado_pago FROM pedidos WHERE pedido_id = :pid"), {"pid": pid}).mappings().first()
                if not pedido or pedido["estado_pago"] == "pagado":
                    continue
                conn.execute(text("UPDATE pedidos SET estado_pago = 'pagado' WHERE pedido_id = :pid"), {"pid": pid})
                pagados += 1

            conn.execute(text("""
                INSERT INTO movimientos_caja (fecha, tipo, categoria, monto, descripcion, sucursal_id, metodo_pago)
                VALUES (NOW() AT TIME ZONE 'America/Panama', 'entrada', 'venta', :monto,
                        'Liquidacion Uber - ' || :n || ' pedidos', :sucursal_id, 'yappy')
            """), {"monto": monto_dep, "n": pagados, "sucursal_id": sucursal_id})

        emitir_dashboard_update()
        return jsonify({"pagados": pagados, "monto": monto_dep}), 200

    except Exception as e:
        current_app.logger.exception(f"Error en liquidacion_uber: {str(e)}")
        return jsonify({"error": "Error interno al procesar la liquidacion"}), 500


@pedido_bp.route("/api/pedidos/pendientes", methods=["GET"])
def get_pedidos_pendientes():
    """Obtiene todos los pedidos con estado_pago = 'pendiente'."""
    try:
        sucursal_id = request.args.get("sucursal_id")
        is_global = not sucursal_id or sucursal_id == "global"

        where_clause = "WHERE p.estado_pago = 'pendiente'"
        params = {}
        if not is_global:
            where_clause += " AND p.sucursal_id = :s_id"
            params["s_id"] = sucursal_id

        sql = f"""
            SELECT p.pedido_id, p.total_pedido, p.metodo_pago, p.tipo_pedido,
                   p.estado_pago, p.fecha, p.sucursal_id
            FROM pedidos p
            {where_clause}
            ORDER BY p.fecha DESC
        """
        from db import fetch_all
        rows = fetch_all(sql, params)
        return jsonify(rows), 200

    except Exception as e:
        current_app.logger.exception(f"Error al obtener pedidos pendientes: {str(e)}")
        return jsonify({"error": "Error interno"}), 500


@pedido_bp.route("/api/pedido", methods=["OPTIONS"])
def handle_options():
    return '', 200
