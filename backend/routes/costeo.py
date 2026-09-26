from flask import Blueprint, request, jsonify, current_app
from db import fetch_all
from utils.costeo_combos import incluir_costeo_combos

costeo_bp = Blueprint("costeo", __name__)

def obtener_costeos():
    # Consulta para obtener el costo total de cada producto sumando sus ingredientes
    sql = """
        SELECT
            r.producto,
            SUM(r.cantidad_requerida * i.costo_unidad) as costo_total,
            p.precio,
            p.precio_delivery,
            json_agg(json_build_object(
                'insumo_id', i.id,
                'nombre_insumo', i.nombre,
                'cantidad', r.cantidad_requerida,
                'unidad', i.unidad_medida,
                'costo_unitario', i.costo_unidad,
                'subtotal', r.cantidad_requerida * i.costo_unidad,
                'stock', i.stock
            )) as ingredientes
        FROM recetas r
        JOIN insumos i ON r.insumo_id = i.id
        LEFT JOIN productos p ON LOWER(p.nombre) = LOWER(r.producto)
        GROUP BY r.producto, p.precio, p.precio_delivery
        ORDER BY r.producto ASC
    """
    resultados = fetch_all(sql)
    productos = fetch_all("SELECT id, nombre, precio, precio_delivery, es_combo, combo_items FROM productos")
    return incluir_costeo_combos(resultados, productos)


@costeo_bp.route("/api/costeo/productos", methods=["GET"])
def get_costeo_productos():
    try:
        resultados = obtener_costeos()
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
        
        resultado = next((c for c in obtener_costeos()
                          if c["producto"].lower() == (producto or "").lower()), None)
        costo_total = float(resultado["costo_total"] or 0) if resultado else 0.0
        
        margen_bruto = precio_venta - costo_total
        porcentaje_margen = (margen_bruto / precio_venta * 100) if precio_venta > 0 else 0
        
        return jsonify({
            "producto": producto,
            "costo_total": costo_total,
            "precio_venta": precio_venta,
            "margen_bruto": margen_bruto,
            "porcentaje_margen": porcentaje_margen,
            "costeo_incompleto": bool(resultado and resultado.get("costeo_incompleto"))
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error en análisis de margen: {e}")
        return jsonify({"error": str(e)}), 500
