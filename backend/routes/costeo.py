from flask import Blueprint, request, jsonify, current_app

costeo_bp = Blueprint("costeo", __name__)

def obtener_costeos():
    from db import engine
    from utils.consumos import CatalogoConsumos
    from decimal import Decimal
    with engine.connect() as conn:
        catalogo = CatalogoConsumos(conn)
        resultados = []
        for p in catalogo.productos.values():
            try:
                consumos = catalogo.producto(p["id"])
                ingredientes = catalogo.detalle(consumos, "ingrediente")
                materiales = catalogo.detalle(consumos, "material")
                resultados.append(dict(producto=p["nombre"], precio=p["precio"], precio_delivery=p.get("precio_delivery"),
                    ingredientes=ingredientes, materiales=materiales, costo_total=catalogo.costo(consumos),
                    costo_ingredientes=sum((i["subtotal"] for i in ingredientes), Decimal(0)),
                    costo_materiales=sum((i["subtotal"] for i in materiales), Decimal(0)), costeo_incompleto=False))
            except ValueError as e:
                resultados.append(dict(producto=p["nombre"], precio=p["precio"], precio_delivery=p.get("precio_delivery"),
                    ingredientes=[], materiales=[], costo_total=None, costo_ingredientes=None, costo_materiales=None,
                    costeo_incompleto=True, error=str(e)))
        return sorted(resultados, key=lambda r: r["producto"].lower())


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
        if not resultado or resultado.get("costeo_incompleto"):
            return jsonify(error="No se puede analizar un producto sin costeo completo"), 422
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
