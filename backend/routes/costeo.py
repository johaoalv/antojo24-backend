from flask import Blueprint, request, jsonify, current_app
from db import fetch_all

costeo_bp = Blueprint("costeo", __name__)

@costeo_bp.route("/api/costeo/productos", methods=["GET"])
def get_costeo_productos():
    try:
        # Consulta para obtener el costo total de cada producto sumando sus ingredientes
        sql = """
            SELECT 
                r.producto,
                SUM(r.cantidad_requerida * i.costo_unidad) as costo_total,
                json_agg(json_build_object(
                    'nombre_insumo', i.nombre,
                    'cantidad', r.cantidad_requerida,
                    'unidad', i.unidad_medida,
                    'costo_unitario', i.costo_unidad,
                    'subtotal', r.cantidad_requerida * i.costo_unidad
                )) as ingredientes
            FROM recetas r
            JOIN insumos i ON r.insumo_id = i.id
            GROUP BY r.producto
            ORDER BY r.producto ASC
        """
        resultados = fetch_all(sql)
        return jsonify(resultados), 200
    except Exception as e:
        current_app.logger.error(f"Error en el costeo de productos: {e}")
        return jsonify({"error": str(e)}), 500

@costeo_bp.route("/api/costeo/analisis", methods=["POST"])
def analizar_margen():
    data = request.json
    try:
        producto = data.get("producto")
        precio_venta = float(data.get("precio_venta", 0))
        
        sql = """
            SELECT SUM(r.cantidad_requerida * i.costo_unidad) as costo_total
            FROM recetas r
            JOIN insumos i ON r.insumo_id = i.id
            WHERE LOWER(r.producto) = LOWER(:producto)
        """
        resultado = fetch_all(sql, {"producto": producto})
        costo_total = float(resultado[0]["costo_total"]) if resultado and resultado[0]["costo_total"] else 0.0
        
        margen_bruto = precio_venta - costo_total
        porcentaje_margen = (margen_bruto / precio_venta * 100) if precio_venta > 0 else 0
        
        return jsonify({
            "producto": producto,
            "costo_total": costo_total,
            "precio_venta": precio_venta,
            "margen_bruto": margen_bruto,
            "porcentaje_margen": porcentaje_margen
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error en análisis de margen: {e}")
        return jsonify({"error": str(e)}), 500
