from flask import Blueprint, request, jsonify, current_app
from db import fetch_all, fetch_one, execute

produccion_bp = Blueprint("produccion", __name__)

@produccion_bp.route("/api/produccion/recetas", methods=["GET"])
def get_recetas_insumos():
    try:
        # Obtenemos solo los insumos que tienen una receta definida
        sql = """
            SELECT DISTINCT i.id, i.nombre, i.unidad_medida, i.sucursal_id, i.stock
            FROM insumos i
            JOIN composicion_insumos ci ON i.id = ci.insumo_compuesto_id
            ORDER BY i.nombre ASC
        """
        recetas = fetch_all(sql)
        return jsonify(recetas), 200
    except Exception as e:
        current_app.logger.error(f"Error al obtener recetas de producción: {e}")
        return jsonify({"error": str(e)}), 500

@produccion_bp.route("/api/produccion/receta/<int:insumo_id>", methods=["GET"])
def get_detalle_receta(insumo_id):
    try:
        sql = """
            SELECT ci.insumo_base_id, i.nombre, ci.cantidad_proporcional, i.unidad_medida, i.costo_unidad, i.stock
            FROM composicion_insumos ci
            JOIN insumos i ON ci.insumo_base_id = i.id
            WHERE ci.insumo_compuesto_id = :id
        """
        detalle = fetch_all(sql, {"id": insumo_id})
        return jsonify(detalle), 200
    except Exception as e:
        current_app.logger.error(f"Error al obtener detalle de receta: {e}")
        return jsonify({"error": str(e)}), 500

@produccion_bp.route("/api/produccion/fabricar", methods=["POST"])
def fabricar_insumo():
    data = request.json
    try:
        insumo_id = data["insumo_compuesto_id"]
        num_tandas = float(data.get("cantidad_a_producir", 1)) # Ahora representa número de tandas
        sucursal_id = data.get("sucursal_id")

        # 1. Obtener la receta
        sql_receta = """
            SELECT ci.insumo_base_id, ci.cantidad_proporcional, i.stock, i.costo_unidad, i.nombre
            FROM composicion_insumos ci
            JOIN insumos i ON ci.insumo_base_id = i.id
            WHERE ci.insumo_compuesto_id = :id
        """
        receta = fetch_all(sql_receta, {"id": insumo_id})
        
        if not receta:
            return jsonify({"error": "No se encontró la receta para este insumo"}), 404

        # 2. Verificar stock de ingredientes
        for item in receta:
            requerido = float(item["cantidad_proporcional"]) * num_tandas
            if float(item["stock"]) < requerido:
                return jsonify({"error": f"Stock insuficiente de {item['nombre']}. Necesitas {requerido} y tienes {item['stock']}"}), 400

        # 3. Procesar: Descontar base y sumar al compuesto
        costo_total_lote = 0
        rendimiento_total = 0 # Suma de todos los ingredientes para obtener el total de la mezcla
        
        for item in receta:
            cantidad_ingrediente = float(item["cantidad_proporcional"]) * num_tandas
            costo_total_lote += cantidad_ingrediente * float(item["costo_unidad"])
            rendimiento_total += cantidad_ingrediente
            
            sql_update_base = "UPDATE insumos SET stock = stock - :req WHERE id = :id"
            execute(sql_update_base, {"req": cantidad_ingrediente, "id": item["insumo_base_id"]})

        # Calcular nuevo costo unidad del compuesto
        nuevo_costo_unidad = costo_total_lote / rendimiento_total if rendimiento_total > 0 else 0

        sql_update_compuesto = """
            UPDATE insumos 
            SET stock = stock + :cant, costo_unidad = :costo
            WHERE id = :id
        """
        execute(sql_update_compuesto, {"cant": rendimiento_total, "costo": nuevo_costo_unidad, "id": insumo_id})

        return jsonify({
            "message": "Producción completada", 
            "tandas": num_tandas,
            "total_producido": rendimiento_total,
            "nuevo_costo": nuevo_costo_unidad
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error en fabricación: {e}")
        return jsonify({"error": str(e)}), 500

@produccion_bp.route("/api/produccion/receta", methods=["POST"])
def guardar_receta():
    data = request.json
    try:
        insumo_compuesto_id = data["insumo_compuesto_id"]
        ingredientes = data["ingredientes"] # Lista de {insumo_base_id, cantidad_proporcional}

        # Borrar receta anterior
        execute("DELETE FROM composicion_insumos WHERE insumo_compuesto_id = :id", {"id": insumo_compuesto_id})

        # Insertar nueva
        for ing in ingredientes:
            sql = """
                INSERT INTO composicion_insumos (insumo_compuesto_id, insumo_base_id, cantidad_proporcional)
                VALUES (:comp, :base, :cant)
            """
            execute(sql, {
                "comp": insumo_compuesto_id,
                "base": ing["insumo_base_id"],
                "cant": ing["cantidad_proporcional"]
            })
        
        return jsonify({"message": "Receta guardada correctamente"}), 201
    except Exception as e:
        current_app.logger.error(f"Error al guardar receta: {e}")
        return jsonify({"error": str(e)}), 500
