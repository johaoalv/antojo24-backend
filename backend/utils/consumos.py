"""Cálculo único de recetas, materiales y combos; sin IDs ni nombres de materiales fijos."""
from decimal import Decimal, InvalidOperation
import json
from sqlalchemy import text


def numero(value, *, cero=False, entero=False):
    try:
        if isinstance(value, bool):
            raise ValueError('Cantidad inválida')
        n = Decimal(str(value))
        if not n.is_finite() or n < 0 or (not cero and n == 0) or (entero and n != n.to_integral_value()):
            raise ValueError('Cantidad inválida')
        return n
    except (InvalidOperation, TypeError):
        raise ValueError('Cantidad inválida') from None


class CatalogoConsumos:
    def __init__(self, conn):
        self.productos = {p['id']: dict(p) for p in conn.execute(text('SELECT * FROM productos')).mappings()}
        self.nombres = {}
        for p in self.productos.values():
            nombre = p['nombre'].strip().lower()
            if nombre in self.nombres:
                raise ValueError(f'Nombre de producto ambiguo: {nombre}')
            self.nombres[nombre] = p['id']
        self.insumos = {i['id']: dict(i) for i in conn.execute(text('SELECT * FROM insumos')).mappings()}
        self.recetas = {}
        for r in conn.execute(text('SELECT * FROM recetas')).mappings():
            i = self.insumos[r['insumo_id']]
            if i['tipo'] != 'ingrediente':
                raise ValueError('Hay materiales dentro de recetas; revise la migración')
            self.recetas.setdefault(r['producto'].strip().lower(), []).append((i['id'], numero(r['cantidad_requerida'])))
        self.materiales = {}
        for r in conn.execute(text('SELECT * FROM producto_materiales')).mappings():
            if self.insumos[r['insumo_id']]['tipo'] != 'material':
                raise ValueError('Asignación de material inválida')
            self.materiales.setdefault(r['producto_id'], []).append((r['insumo_id'], numero(r['cantidad'])))
        self.por_pedido = [dict(r) for r in conn.execute(text('SELECT * FROM materiales_por_pedido ORDER BY codigo')).mappings()]
        if not self.por_pedido:
            raise ValueError('Falta configurar los materiales por pedido')
        for r in self.por_pedido:
            if self.insumos[r['insumo_id']]['tipo'] != 'material':
                raise ValueError('Material por pedido inválido')

    def producto(self, producto_id, camino=()):
        if producto_id in camino:
            raise ValueError('El combo contiene una referencia circular')
        p = self.productos.get(producto_id)
        if not p:
            raise ValueError('El combo contiene un producto eliminado')
        resultado = {}
        if p['es_combo']:
            componentes = p.get('combo_items') or []
            if isinstance(componentes, str):
                componentes = json.loads(componentes)
            if not componentes:
                raise ValueError(f'Combo sin componentes: {p["nombre"]}')
            for item in componentes:
                for i, cantidad in self.producto(int(item['id']), camino + (producto_id,)).items():
                    resultado[i] = resultado.get(i, Decimal(0)) + cantidad * numero(item.get('cantidad', 1))
        else:
            receta = self.recetas.get(p['nombre'].strip().lower())
            if not receta:
                raise ValueError(f'Falta receta de {p["nombre"]}')
            for i, cantidad in receta:
                resultado[i] = resultado.get(i, Decimal(0)) + cantidad
        for i, cantidad in self.materiales.get(producto_id, []):
            resultado[i] = resultado.get(i, Decimal(0)) + cantidad
        return resultado

    def costo(self, consumos):
        total = Decimal(0)
        for i, cantidad in consumos.items():
            costo = numero(self.insumos[i]['costo_unidad'], cero=True)
            total += costo * cantidad
        return total

    def detalle(self, consumos, tipo):
        return [dict(insumo_id=i, nombre_insumo=self.insumos[i]['nombre'], cantidad=c,
                     unidad=self.insumos[i]['unidad_medida'], stock=self.insumos[i]['stock'],
                     costo_unitario=self.insumos[i]['costo_unidad'],
                     subtotal=c * numero(self.insumos[i]['costo_unidad'], cero=True))
                for i, c in sorted(consumos.items()) if self.insumos[i]['tipo'] == tipo]

    def pedido(self, items, ajustes=None):
        if not isinstance(items, list) or not items:
            raise ValueError('El pedido debe contener productos')
        ajustes = ajustes or {}
        permitidos = {r['codigo'] for r in self.por_pedido}
        if set(ajustes) - permitidos:
            raise ValueError('Material por pedido desconocido')
        total, lineas = {}, []
        for item in items:
            pid = self.nombres.get(str(item.get('producto', '')).strip().lower())
            if pid is None:
                raise ValueError('Producto desconocido')
            p = self.productos[pid]
            if p.get('disponible') is False:
                raise ValueError(f'Producto no disponible: {p["nombre"]}')
            cantidad = numero(item.get('cantidad'), entero=True)
            unitario = self.producto(pid)
            lineas.append(dict(producto_id=pid, costo_unitario=self.costo(unitario)))
            for i, c in unitario.items():
                total[i] = total.get(i, Decimal(0)) + c * cantidad
        for r in self.por_pedido:
            cantidad = numero(ajustes.get(r['codigo'], r['cantidad']), cero=True, entero=True)
            if cantidad:
                i = r['insumo_id']
                total[i] = total.get(i, Decimal(0)) + cantidad
        return total, lineas


def guardar_consumos(conn, pedido_id, consumos):
    # Orden estable de bloqueo para pedidos concurrentes.
    for i, cantidad in sorted(consumos.items()):
        row = conn.execute(text('SELECT nombre, stock, costo_unidad, tipo FROM insumos WHERE id=:id FOR UPDATE'), {'id': i}).mappings().one()
        if Decimal(str(row['stock'] or 0)) < cantidad:
            raise ValueError(f'Stock insuficiente de {row["nombre"]}')
        conn.execute(text('INSERT INTO pedido_consumos(pedido_id,insumo_id,cantidad,costo_unitario,tipo) VALUES (:pid,:id,:cantidad,:costo,:tipo)'),
                     dict(pid=pedido_id, id=i, cantidad=cantidad, costo=row['costo_unidad'], tipo=row['tipo']))
        conn.execute(text('UPDATE insumos SET stock=stock-:cantidad WHERE id=:id'), dict(id=i, cantidad=cantidad))


def consumos_legacy(conn, pedido_id):
    """Compatibilidad con cancelaciones anteriores; no es un historial exacto."""
    catalogo = CatalogoConsumos(conn)
    recetas = {}
    rows = conn.execute(text('''SELECT producto, insumo_id, cantidad_requerida FROM recetas
        UNION ALL SELECT producto, insumo_id, cantidad_requerida FROM recetas_materiales_migradas''')).mappings()
    for r in rows:
        recetas.setdefault(r['producto'].strip().lower(), []).append(r)
    total = {}
    for item in conn.execute(text('SELECT producto,cantidad FROM productos_pedido WHERE pedido_id=:pid'), {'pid': pedido_id}).mappings():
        nombre = item['producto'].strip().lower()
        p = catalogo.productos.get(catalogo.nombres.get(nombre))
        bases = [(nombre, numero(item['cantidad']))]
        if p and p['es_combo']:
            componentes = p['combo_items'] or []
            if isinstance(componentes, str):
                componentes = json.loads(componentes)
            bases = []
            for componente in componentes:
                base = catalogo.productos.get(int(componente['id']))
                if not base:
                    raise ValueError('No se puede reconstruir un pedido antiguo: componente eliminado')
                bases.append((base['nombre'].strip().lower(), numero(componente.get('cantidad', 1)) * numero(item['cantidad'])))
        for base, cantidad in bases:
            if base not in recetas:
                raise ValueError('No se puede reconstruir un pedido antiguo: falta su receta')
            for r in recetas[base]:
                i = r['insumo_id']
                if i not in catalogo.insumos:
                    raise ValueError('Un insumo histórico fue eliminado; requiere conciliación')
                total[i] = total.get(i, Decimal(0)) + cantidad * numero(r['cantidad_requerida'])
    return [dict(insumo_id=i, cantidad=c, nombre=catalogo.insumos[i]['nombre']) for i, c in sorted(total.items())]
