from flask import Blueprint, request, jsonify
from sqlalchemy import text
from db import engine
from utils.consumos import numero

materiales_bp = Blueprint('materiales', __name__)


@materiales_bp.route('/api/materiales', methods=['GET'])
def obtener_materiales():
    with engine.connect() as conn:
        materiales = [dict(r) for r in conn.execute(text("SELECT * FROM insumos WHERE tipo='material' ORDER BY nombre")).mappings()]
        productos = [dict(r) for r in conn.execute(text('SELECT pm.*,p.nombre AS producto,i.nombre AS material FROM producto_materiales pm JOIN productos p ON p.id=pm.producto_id JOIN insumos i ON i.id=pm.insumo_id ORDER BY p.nombre,i.nombre')).mappings()]
        pedido = [dict(r) for r in conn.execute(text('SELECT mp.*,i.nombre,i.costo_unidad FROM materiales_por_pedido mp JOIN insumos i ON i.id=mp.insumo_id ORDER BY mp.codigo')).mappings()]
        return jsonify(materiales=materiales, productos=productos, pedido=pedido)


@materiales_bp.route('/api/materiales/productos/<int:producto_id>/<int:insumo_id>', methods=['PUT', 'DELETE'])
def asignar_material(producto_id, insumo_id):
    try:
        with engine.begin() as conn:
            p = conn.execute(text('SELECT es_combo FROM productos WHERE id=:id'), {'id': producto_id}).mappings().first()
            if not p:
                return jsonify(error='Producto no encontrado'), 404
            if p['es_combo']:
                return jsonify(error='Configure materiales en los componentes del combo'), 400
            if request.method == 'DELETE':
                conn.execute(text('DELETE FROM producto_materiales WHERE producto_id=:p AND insumo_id=:i'), dict(p=producto_id,i=insumo_id))
            else:
                cantidad = numero((request.get_json() or {}).get('cantidad'))
                m = conn.execute(text("SELECT id FROM insumos WHERE id=:id AND tipo='material'"), {'id': insumo_id}).first()
                if not m:
                    return jsonify(error='Seleccione un material'), 400
                if conn.execute(text('SELECT 1 FROM materiales_por_pedido WHERE insumo_id=:id'), {'id': insumo_id}).first():
                    return jsonify(error='Este material se aplica por pedido; no debe duplicarse por producto'), 400
                conn.execute(text('INSERT INTO producto_materiales(producto_id,insumo_id,cantidad) VALUES (:p,:i,:c) ON CONFLICT(producto_id,insumo_id) DO UPDATE SET cantidad=EXCLUDED.cantidad'), dict(p=producto_id,i=insumo_id,c=cantidad))
        return jsonify(message='Materiales actualizados')
    except ValueError as e:
        return jsonify(error=str(e)), 400


@materiales_bp.route('/api/materiales/pedido/<codigo>', methods=['PUT'])
def configurar_material_pedido(codigo):
    try:
        cantidad = numero((request.get_json() or {}).get('cantidad'), cero=True, entero=True)
        with engine.begin() as conn:
            result = conn.execute(text('UPDATE materiales_por_pedido SET cantidad=:c WHERE codigo=:codigo'), dict(c=cantidad,codigo=codigo))
            if not result.rowcount:
                return jsonify(error='Configuración no encontrada'), 404
        return jsonify(message='Cantidad predeterminada actualizada')
    except ValueError as e:
        return jsonify(error=str(e)), 400
