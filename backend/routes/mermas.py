from flask import Blueprint, request, jsonify, current_app
from db import fetch_all, fetch_one, execute

mermas_bp = Blueprint("mermas", __name__)

MOTIVOS_VALIDOS = ["Derrame", "Vencimiento", "Daño", "Ajuste Manual", "Robo", "Otro"]

@mermas_bp.route("/api/mermas", methods=["GET"])
def get_mermas():
    try:
        sucursal_id = request.args.get("sucursal_id")
        
        sql = """
            SELECT m.id, m.cantidad, m.motivo, m.observacion, m.fecha, m.sucursal_id,
                   i.nombre as nombre_insumo, i.unidad_medida, i.costo_unidad,
                   ROUND(m.cantidad * i.costo_unidad, 4) as costo_perdido
            FROM mermas m
            JOIN insumos i ON m.insumo_id = i.id
        """
        params = {}
        if sucursal_id and sucursal_id != "global":
            sql += " WHERE m.sucursal_id = :suc"
            params["suc"] = sucursal_id
        
        sql += " ORDER BY m.fecha DESC LIMIT 100"
        
        mermas = fetch_all(sql, params)
        return jsonify(mermas), 200
    except Exception as e:
        current_app.logger.error(f"Error al obtener mermas: {e}")
        return jsonify({"error": str(e)}), 500

@mermas_bp.route("/api/mermas/resumen", methods=["GET"])
def get_resumen_mermas():
    try:
        sucursal_id = request.args.get("sucursal_id")
        
        where_parts = ["m.fecha >= NOW() - INTERVAL '30 days'"]
        params = {}
        
        if sucursal_id and sucursal_id != "global":
            where_parts.append("m.sucursal_id = :suc")
            params["suc"] = sucursal_id
        
        where_clause = " AND ".join(where_parts)
        
        sql = f"""
            SELECT m.motivo, 
                   COUNT(*) as total_registros,
                   SUM(ROUND(m.cantidad * i.costo_unidad, 4)) as total_perdido
            FROM mermas m
            JOIN insumos i ON m.insumo_id = i.id
            WHERE {where_clause}
            GROUP BY m.motivo
            ORDER BY total_perdido DESC
        """
        resumen = fetch_all(sql, params)
        return jsonify(resumen), 200
    except Exception as e:
        current_app.logger.error(f"Error al obtener resumen de mermas: {e}")
        return jsonify({"error": str(e)}), 500

@mermas_bp.route("/api/mermas", methods=["POST"])
def registrar_merma():
    data = request.json
    try:
        insumo_id = data["insumo_id"]
        cantidad = float(data["cantidad"])
        motivo = data["motivo"]
        observacion = data.get("observacion", "")
        sucursal_id = data.get("sucursal_id")

        if motivo not in MOTIVOS_VALIDOS:
            return jsonify({"error": f"Motivo inválido. Use: {', '.join(MOTIVOS_VALIDOS)}"}), 400

        # Verificar que el insumo existe y tiene stock suficiente
        insumo = fetch_one("SELECT id, nombre, stock FROM insumos WHERE id = :id", {"id": insumo_id})
        if not insumo:
            return jsonify({"error": "Insumo no encontrado"}), 404

        if float(insumo["stock"]) < cantidad:
            return jsonify({"error": f"Stock insuficiente de {insumo['nombre']}. Tienes {insumo['stock']} y quieres descontar {cantidad}"}), 400

        # 1. Registrar la merma
        sql_merma = """
            INSERT INTO mermas (insumo_id, cantidad, motivo, observacion, sucursal_id)
            VALUES (:insumo, :cant, :motivo, :obs, :suc)
        """
        execute(sql_merma, {
            "insumo": insumo_id,
            "cant": cantidad,
            "motivo": motivo,
            "obs": observacion,
            "suc": sucursal_id
        })

        # 2. Descontar del stock
        execute("UPDATE insumos SET stock = stock - :cant WHERE id = :id", {"cant": cantidad, "id": insumo_id})

        return jsonify({"message": f"Merma registrada: {cantidad} de {insumo['nombre']} descontados"}), 201
    except Exception as e:
        current_app.logger.error(f"Error al registrar merma: {e}")
        return jsonify({"error": str(e)}), 500
