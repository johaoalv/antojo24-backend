from flask import Blueprint, request, jsonify, current_app
from db import fetch_all
import json

costeo_bp = Blueprint("costeo", __name__)

@costeo_bp.route("/api/costeo/productos", methods=["GET"])
def get_costeo_productos():
    try:
        # 1. Costeos de productos con recetas (Base)
        sql_base = """
            SELECT
                r.producto,
                SUM(r.cantidad_requerida * i.costo_unidad) as costo_total,
                p.precio,
                p.precio_delivery,
                json_agg(json_build_object(
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
        """
        resultados = fetch_all(sql_base)
        
        # Mapear costo por nombre de producto para usarlo en combos
        mapa_costos = {}
        for r in resultados:
            # fetch_all returns RealDictRow or dict depending on db implementation
            prod_name = r["producto"].lower() if r["producto"] else ""
            mapa_costos[prod_name] = float(r["costo_total"] or 0)

        # Convertir a lista de diccionarios para poder agregar combos
        resultados_lista = [dict(r) for r in resultados]

        # 2. Obtener y procesar Combos
        sql_combos = """
            SELECT nombre as producto, precio, precio_delivery, combo_items
            FROM productos
            WHERE es_combo = true
        """
        combos = fetch_all(sql_combos)
        
        for combo in combos:
            items_combo = []
            if combo["combo_items"]:
                try:
                    if isinstance(combo["combo_items"], list):
                        items_combo = combo["combo_items"]
                    else:
                        items_combo = json.loads(combo["combo_items"])
                except Exception:
                    pass

            costo_total_combo = 0.0
            ingredientes_combo = []
            
            for item in items_combo:
                # Cada item del combo normalmente tiene 'nombre' o al menos 'id'. 
                # Dependiendo de cómo lo guarden, extraemos el nombre.
                sub_nombre = item.get("nombre", "").lower()
                cant = float(item.get("cantidad", 1))
                costo_unitario = mapa_costos.get(sub_nombre, 0.0)
                subtotal = cant * costo_unitario
                costo_total_combo += subtotal
                
                ingredientes_combo.append({
                    'nombre_insumo': item.get("nombre", f"Producto ID {item.get('id')}"),
                    'cantidad': cant,
                    'unidad': 'unid',
                    'costo_unitario': costo_unitario,
                    'subtotal': subtotal,
                    'stock': 0
                })

            resultados_lista.append({
                "producto": combo["producto"],
                "costo_total": costo_total_combo,
                "precio": float(combo["precio"] or 0),
                "precio_delivery": float(combo["precio_delivery"] or 0),
                "ingredientes": ingredientes_combo
            })

        # Ordenar todo alfabéticamente
        resultados_lista.sort(key=lambda x: str(x.get("producto", "")).lower())

        return jsonify(resultados_lista), 200
    except Exception as e:
        current_app.logger.error(f"Error en el costeo de productos: {e}")
        return jsonify({"error": str(e)}), 500

@costeo_bp.route("/api/costeo/analisis", methods=["POST"])
def analizar_margen():
    data = request.json
    try:
        producto = data.get("producto", "")
        precio_venta = float(data.get("precio_venta", 0))
        
        # Saber si es combo
        sql_prod = "SELECT es_combo, combo_items FROM productos WHERE LOWER(nombre) = LOWER(:producto)"
        prod = fetch_all(sql_prod, {"producto": producto})
        
        costo_total = 0.0
        
        if prod and prod[0]["es_combo"]:
            # Es combo, calcular basado en sus items
            items_combo = []
            try:
                if isinstance(prod[0]["combo_items"], list):
                    items_combo = prod[0]["combo_items"]
                else:
                    items_combo = json.loads(prod[0]["combo_items"] or "[]")
            except Exception:
                pass
            
            for item in items_combo:
                sub_nombre = item.get("nombre", "")
                cant = float(item.get("cantidad", 1))
                
                sql_sub = """
                    SELECT SUM(r.cantidad_requerida * i.costo_unidad) as costo_total
                    FROM recetas r
                    JOIN insumos i ON r.insumo_id = i.id
                    WHERE LOWER(r.producto) = LOWER(:producto)
                """
                res_sub = fetch_all(sql_sub, {"producto": sub_nombre})
                sub_costo = float(res_sub[0]["costo_total"]) if res_sub and res_sub[0]["costo_total"] else 0.0
                costo_total += sub_costo * cant
                
        else:
            # Producto normal
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
