from flask import Blueprint, request, jsonify, current_app
from db import fetch_all, fetch_one, execute

recetas_bp = Blueprint("recetas", __name__)

@recetas_bp.route("/api/recetas", methods=["GET"])
def get_all_recetas():
    try:
        # Obtenemos todas las recetas con el nombre del insumo
        sql = """
            SELECT r.id, r.producto, r.insumo_id, i.nombre as nombre_insumo, r.cantidad_requerida, i.unidad_medida
            FROM recetas r
            JOIN insumos i ON r.insumo_id = i.id
            WHERE i.tipo = 'ingrediente'
            ORDER BY r.producto ASC, i.nombre ASC
        """
        recetas = fetch_all(sql)
        
        # Agrupamos por producto para facilitar el manejo en el frontend
        productos = {}
        for r in recetas:
            prod = r["producto"]
            if prod not in productos:
                productos[prod] = []
            productos[prod].append(r)
            
        return jsonify(productos), 200
    except Exception as e:
        current_app.logger.error(f"Error al obtener recetas: {e}")
        return jsonify({"error": str(e)}), 500

@recetas_bp.route("/api/recetas", methods=["POST"])
def add_ingrediente():
    data = request.json
    try:
        producto = data["producto"].lower()
        insumo_id = data["insumo_id"]
        cantidad = data["cantidad_requerida"]
        if not fetch_one("SELECT id FROM insumos WHERE id=:id AND tipo='ingrediente'", {"id": insumo_id}):
            return jsonify({"error": "Las recetas solo admiten ingredientes; configure los materiales aparte"}), 400
        
        sql = """
            INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
            VALUES (:prod, :insumo, :cant)
            RETURNING id
        """
        result = execute(sql, {"prod": producto, "insumo": insumo_id, "cant": cantidad})
        return jsonify({"message": "Ingrediente añadido", "id": result}), 201
    except Exception as e:
        current_app.logger.error(f"Error al añadir ingrediente: {e}")
        return jsonify({"error": str(e)}), 500

@recetas_bp.route("/api/recetas/bulk", methods=["POST", "OPTIONS"])
def add_receta_bulk():
    if request.method == "OPTIONS":
        return "", 200
    data = request.json
    try:
        producto = data["producto"].lower()
        ingredientes = data["ingredientes"] # Lista de {insumo_id, cantidad_requerida}
        
        # Primero eliminamos ingredientes previos si existieran para este producto (opcional, pero util para sobreescribir)
        # execute("DELETE FROM recetas WHERE LOWER(producto) = :prod", {"prod": producto})
        
        for ing in ingredientes:
            if not fetch_one("SELECT id FROM insumos WHERE id=:id AND tipo='ingrediente'", {"id": ing["insumo_id"]}):
                return jsonify({"error": "Las recetas solo admiten ingredientes"}), 400
        for ing in ingredientes:
            sql = """
                INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
                VALUES (:prod, :insumo, :cant)
            """
            execute(sql, {"prod": producto, "insumo": ing["insumo_id"], "cant": ing["cantidad_requerida"]})
            
        return jsonify({"message": f"Receta para {producto} creada con {len(ingredientes)} ingredientes"}), 201
    except Exception as e:
        current_app.logger.error(f"Error al crear receta bulk: {e}")
        return jsonify({"error": str(e)}), 500

@recetas_bp.route("/api/recetas/<int:id>", methods=["PUT", "DELETE", "OPTIONS"])
def update_delete_ingrediente(id):
    if request.method == "OPTIONS":
        return "", 200
    if request.method == "PUT":
        data = request.json
        try:
            cantidad = data["cantidad_requerida"]
            sql = "UPDATE recetas SET cantidad_requerida = :cant WHERE id = :id"
            execute(sql, {"cant": cantidad, "id": id})
            return jsonify({"message": "Cantidad actualizada"}), 200
        except Exception as e:
            current_app.logger.error(f"Error al actualizar ingrediente: {e}")
            return jsonify({"error": str(e)}), 500
    elif request.method == "DELETE":
        try:
            sql = "DELETE FROM recetas WHERE id = :id"
            execute(sql, {"id": id})
            return jsonify({"message": "Ingrediente eliminado de la receta"}), 200
        except Exception as e:
            current_app.logger.error(f"Error al eliminar ingrediente: {e}")
            return jsonify({"error": str(e)}), 500

@recetas_bp.route("/api/recetas", methods=["OPTIONS"])
def handle_options_root():
    return "", 200


@recetas_bp.route("/api/public/ingredientes", methods=["GET"])
def ingredientes_publicos():
    from db import engine
    from utils.consumos import CatalogoConsumos
    with engine.connect() as conn:
        catalogo = CatalogoConsumos(conn)
        resultado = {}
        for p in catalogo.productos.values():
            try:
                resultado[p["nombre"]] = [{"nombre_insumo": i["nombre_insumo"]}
                    for i in catalogo.detalle(catalogo.producto(p["id"]), "ingrediente")]
            except ValueError:
                resultado[p["nombre"]] = []
        return jsonify(resultado)
