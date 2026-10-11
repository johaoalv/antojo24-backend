from flask import Blueprint, request, jsonify, current_app
from utils.emit_dashboard_update import emitir_dashboard_update
from utils.emit_stock_alerts import emitir_stock_alerts
from db import engine
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from utils.consumos import CatalogoConsumos, guardar_consumos, consumos_legacy

pedido_bp = Blueprint("pedido", __name__)


@pedido_bp.route("/api/pedido", methods=["POST"])
def pedido():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data.get("pedido_id") or not isinstance(data.get("pedido"), list):
        return jsonify(error="Pedido inválido"), 400
    current_app.logger.debug(f"Procesando pedido {data['pedido_id']}")

    # --- Lógica para pagos simples y mixtos ---
    monto_recibido = None
    monto_vuelto = None
    response_data = {"message": "Pedido insertado correctamente"}
    es_pago_mixto = False
    metodos_pago_detalles = None

    # Detectar si es pago mixto o simple
    metodos_pago_detalles = data.get("metodos_pago_detalles")
    es_pago_mixto = metodos_pago_detalles and len(metodos_pago_detalles) > 1

    if es_pago_mixto:
        try:
            total_pedido = float(data.get("total_pedido", 0))
            suma_montos = sum(float(m.get("monto", 0)) for m in metodos_pago_detalles)

            if abs(suma_montos - total_pedido) > 0.01:
                return jsonify({"error": f"Suma de pagos ({suma_montos:.2f}) no coincide con total ({total_pedido:.2f})"}), 400

            current_app.logger.info(f"💳 Pago MIXTO detectado: {len(metodos_pago_detalles)} métodos")
            for m in metodos_pago_detalles:
                current_app.logger.info(f"   - {m.get('metodo_pago')}: ${m.get('monto'):.2f}")

            # Calcular vuelto solo si hay efectivo en la mezcla
            for m in metodos_pago_detalles:
                if m.get("metodo_pago") == "efectivo":
                    monto_recibido = float(data.get("monto_recibido", m.get("monto")))
                    monto_en_efectivo = float(m.get("monto", 0))
                    monto_vuelto = monto_recibido - monto_en_efectivo
                    current_app.logger.info(f"💵 Vuelto en efectivo: ${monto_vuelto:.2f}")
                    response_data["monto_vuelto"] = round(monto_vuelto, 2)
                    break

            response_data["es_pago_mixto"] = True
        except (ValueError, TypeError) as e:
            current_app.logger.error(f"Error en pago mixto: {e}")
            return jsonify({"error": "Datos inválidos en metodos_pago_detalles"}), 400
    else:
        # Pago simple (comportamiento actual)
        metodo_pago_principal = data.get("metodo_pago")
        if metodo_pago_principal == "efectivo":
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

        # Convertir pago simple a formato de detalles para unificar la lógica
        metodos_pago_detalles = [{"metodo_pago": metodo_pago_principal, "monto": data.get("total_pedido")}]

    try:
        # Mismo snapshot para costos y stock, dentro de la transacción de venta.
        with engine.begin() as conn:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            existente = conn.execute(text("SELECT 1 FROM pedidos WHERE pedido_id=:pid"), {"pid": data["pedido_id"]}).first()
            if existente:
                return jsonify({"error": "Este pedido ya fue registrado"}), 409
            catalogo = CatalogoConsumos(conn)
            ajustes = data.get("materiales_pedido", {})
            if not isinstance(ajustes, dict):
                raise ValueError("Materiales del pedido inválidos")
            ajustes = dict(ajustes)
            if "bolsas" in data:
                ajustes["bolsas"] = data["bolsas"]
            consumos, lineas = catalogo.pedido(data.get("pedido"), ajustes)
            costo_total_pedido = catalogo.costo(consumos)
            # 1. Insertar el pedido principal con costo_total
            # Para pago mixto, guardar el método principal (el primero o el de mayor monto)
            if es_pago_mixto:
                metodo_principal = max(metodos_pago_detalles, key=lambda x: float(x.get("monto", 0))).get("metodo_pago")
            else:
                metodo_principal = data.get("metodo_pago")

            sql_pedido = """
                INSERT INTO pedidos (pedido_id, total_pedido, metodo_pago, sucursal_id, fecha, monto_recibido, monto_vuelto, costo_total, tipo_pedido, estado_pago, consumos_registrados)
                VALUES (:pedido_id, :total_pedido, :metodo_pago, :sucursal_id, :fecha, :monto_recibido, :monto_vuelto, :costo_total, :tipo_pedido, :estado_pago, TRUE)
            """
            params_pedido = {
                "pedido_id": data["pedido_id"],
                "total_pedido": data["total_pedido"],
                "metodo_pago": metodo_principal,
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

            for item, linea in zip(data["pedido"], lineas):
                p_id = linea["producto_id"]
                costo_u = linea["costo_unitario"]

                conn.execute(text(sql_productos), {
                    "pedido_id": data["pedido_id"],
                    "producto": item["producto"],
                    "cantidad": item["cantidad"],
                    "total_item": item["total_item"],
                    "metodo_pago": metodo_principal,
                    "sucursal_id": data["sucursal_id"],
                    "fecha": data["fecha"],
                    "costo_unitario": costo_u,
                    "producto_id": p_id
                })
            
            # 3. Registrar el MOVIMIENTO DE CAJA (Solo si el pago ya fue recibido)
            estado_pago = data.get("estado_pago", "pagado")
            if estado_pago != "pendiente":
                # Si es pago mixto, insertar un registro por cada método
                if es_pago_mixto:
                    sql_movimiento = """
                        INSERT INTO movimientos_caja (fecha, tipo, categoria, monto, descripcion, sucursal_id, referencia_id, metodo_pago)
                        VALUES (:fecha, 'entrada', 'venta', :monto, :descripcion, :sucursal_id, :referencia_id, :metodo_pago)
                    """
                    for m in metodos_pago_detalles:
                        monto_metodo = float(m.get("monto", 0))
                        metodo = m.get("metodo_pago")
                        conn.execute(text(sql_movimiento), {
                            "fecha": data["fecha"],
                            "monto": monto_metodo,
                            "descripcion": f"Venta registrada (MIXTO) - ID: {data['pedido_id']}",
                            "sucursal_id": data["sucursal_id"],
                            "referencia_id": data["pedido_id"],
                            "metodo_pago": metodo
                        })
                        current_app.logger.info(f"   ✓ Movimiento caja: {metodo} ${monto_metodo:.2f} (ref: {data['pedido_id']})")
                else:
                    # Pago simple: insertar un registro único
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
                        "metodo_pago": metodo_principal
                    })
            else:
                current_app.logger.info(f"⏳ Pedido {data['pedido_id']} pendiente de pago (delivery). Movimiento de caja diferido.")
            
            guardar_consumos(conn, data["pedido_id"], consumos)

            current_app.logger.info(f"✅ Pedido {data['pedido_id']} completado y stock actualizado.")
            
        current_app.logger.info("🚀 Emitiendo actualización de dashboard vía WebSocket...")
        emitir_dashboard_update()
        emitir_stock_alerts()
        return jsonify(response_data), 201
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except OperationalError as e:
        if getattr(e.orig, "pgcode", None) in ("40001", "40P01"):
            return jsonify(error="El inventario cambió durante la venta. Reintenta confirmar."), 409
        current_app.logger.exception("Error de base de datos al registrar pedido")
        return jsonify(error="No se pudo registrar el pedido"), 500
    except IntegrityError:
        return jsonify({"error": "El pedido ya existe o contiene una referencia inválida"}), 409
    except Exception as e:
        current_app.logger.exception(f"Error al procesar pedido: {str(e)}")
        return jsonify({"error": "Error interno al procesar el pedido"}), 500


@pedido_bp.route("/api/pedido/<pedido_id>", methods=["DELETE"])
def eliminar_pedido(pedido_id):
    current_app.logger.info(f"🗑️ Solicitud para eliminar pedido: {pedido_id}")
    try:
        restored_items = []
        with engine.begin() as conn:
            pedido = conn.execute(text("SELECT consumos_registrados FROM pedidos WHERE pedido_id=:pid FOR UPDATE"), {"pid": pedido_id}).mappings().first()
            if not pedido:
                return jsonify({"error": "Pedido no encontrado"}), 404
            if pedido["consumos_registrados"]:
                consumos = conn.execute(text("SELECT c.insumo_id, c.cantidad, i.nombre FROM pedido_consumos c JOIN insumos i ON i.id=c.insumo_id WHERE c.pedido_id=:pid ORDER BY c.insumo_id"), {"pid": pedido_id}).mappings().all()
            else:
                # Compatibilidad: conservar la reconstrucción histórica, incluyendo
                # materiales retirados de recetas. No inventar bolsas no registradas.
                consumos = consumos_legacy(conn, pedido_id)
            for consumo in consumos:
                conn.execute(text("UPDATE insumos SET stock=stock+:cantidad WHERE id=:id"),
                             {"cantidad": consumo["cantidad"], "id": consumo["insumo_id"]})
                restored_items.append({"insumo": consumo["nombre"], "cantidad": consumo["cantidad"]})

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

    except ValueError as e:
        return jsonify(error=str(e)), 409
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
