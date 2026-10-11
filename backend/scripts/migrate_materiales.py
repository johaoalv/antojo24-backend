"""Preview de solo lectura por defecto; --apply requiere ventana sin ventas."""
import argparse
import json
import os
from pathlib import Path
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

VERSION = '20260927_materiales'
# Identificación inicial revisable; los IDs se resuelven en CADA entorno.
MATERIALES = {
    'bolsa_entrega': 'bolsa de entrega',
    'papel_antigrasa': 'papel antigrasa',
    'servilleta': 'servilletas',
    'caja_papas': 'caja de papas',
    'envase_salsa': 'envase de salsas',
    'tapa_salsa': 'tapa de salsas',
}


def normalizar(value):
    return value.strip().lower()


def planificar(insumos, productos, recetas):
    materiales = {}
    errores = []
    for codigo, nombre in MATERIALES.items():
        matches = [i for i in insumos if normalizar(i['nombre']) == nombre]
        if len(matches) != 1:
            errores.append(f'{codigo}: se esperaba una coincidencia, encontradas {len(matches)}')
            continue
        materiales[codigo] = matches[0]
    if errores:
        raise ValueError('; '.join(errores))
    por_nombre = {}
    for p in productos:
        key = normalizar(p['nombre'])
        if key in por_nombre:
            raise ValueError(f'Producto ambiguo: {key}')
        por_nombre[key] = p
    ids = {i['id'] for i in materiales.values()}
    bolsa = materiales['bolsa_entrega']['id']
    asignaciones = {}
    retiradas = []
    for r in recetas:
        if r['insumo_id'] not in ids:
            continue
        retiradas.append(r)
        p = por_nombre.get(normalizar(r['producto']))
        # Recetas huérfanas y recetas directas de combos se archivan, no se heredan.
        if not p or p['es_combo'] or r['insumo_id'] == bolsa:
            continue
        key = (p['id'], r['insumo_id'])
        if key in asignaciones:
            raise ValueError(f'Material duplicado en receta de {p["nombre"]}')
        cantidad = Decimal(str(r['cantidad_requerida']))
        if not cantidad.is_finite() or cantidad <= 0:
            raise ValueError(f'Cantidad inválida en {p["nombre"]}')
        asignaciones[key] = cantidad
    # Los productos que ya usaban papel/servilleta reciben una unidad de ambos.
    papel = materiales['papel_antigrasa']['id']
    servilleta = materiales['servilleta']['id']
    principales = {p for p, i in asignaciones if i in (papel, servilleta)}
    for p in principales:
        asignaciones[p, papel] = Decimal(1)
        asignaciones[p, servilleta] = Decimal(1)
    return materiales, asignaciones, retiradas


def migrar(conn, apply=False):
    with conn.cursor(cursor_factory=RealDictCursor) as q:
        q.execute("SET LOCAL lock_timeout = '5s'")
        q.execute("SELECT to_regclass('schema_migrations') AS tabla")
        if q.fetchone()['tabla']:
            q.execute('SELECT 1 FROM schema_migrations WHERE version=%s', (VERSION,))
            if q.fetchone():
                return {'estado': 'ya aplicada; no se modificó nada'}
        if apply:
            q.execute('LOCK TABLE insumos, productos, recetas, pedidos IN ACCESS EXCLUSIVE MODE')
        q.execute('SELECT * FROM insumos ORDER BY id'); insumos = q.fetchall()
        q.execute('SELECT * FROM productos ORDER BY id'); productos = q.fetchall()
        q.execute('SELECT * FROM recetas ORDER BY id'); recetas = q.fetchall()
        materiales, asignaciones, retiradas = planificar(insumos, productos, recetas)
        informe = {'estado': 'aplicada' if apply else 'preview, sin cambios',
                   'materiales': {k: {'id_local': v['id'], 'nombre': v['nombre'], 'stock': v['stock'], 'costo': v['costo_unidad']} for k, v in materiales.items()},
                   'asignaciones': [{'producto_id_local': p, 'insumo_id_local': i, 'cantidad': c} for (p, i), c in asignaciones.items()],
                   'recetas_a_archivar': [dict(r) for r in retiradas],
                   'advertencia': 'Pedidos históricos: restitución aproximada compatible con recetas actuales y materiales archivados; bolsas antiguas no recuperables.'}
        if not apply:
            return informe
        q.execute((Path(__file__).resolve().parents[1] / 'migrations' / f'{VERSION}.sql').read_text())
        for codigo, i in materiales.items():
            if i.get('codigo') not in (None, codigo):
                raise ValueError(f'Código existente incompatible para {i["nombre"]}')
            q.execute("UPDATE insumos SET tipo='material', codigo=%s WHERE id=%s", (codigo, i['id']))
        for (p, i), cantidad in asignaciones.items():
            q.execute('INSERT INTO producto_materiales VALUES (%s,%s,%s)', (p, i, cantidad))
        q.execute('INSERT INTO materiales_por_pedido VALUES (%s,%s,1)', ('bolsas', materiales['bolsa_entrega']['id']))
        for r in retiradas:
            q.execute('INSERT INTO recetas_materiales_migradas VALUES (%s,%s,%s,%s)',
                      (r['id'], r['producto'], r['insumo_id'], r['cantidad_requerida']))
            q.execute('DELETE FROM recetas WHERE id=%s', (r['id'],))
        q.execute('INSERT INTO schema_migrations(version) VALUES (%s)', (VERSION,))
        q.execute('SELECT id,stock,costo_unidad FROM insumos ORDER BY id')
        if [(i['id'], i['stock'], i['costo_unidad']) for i in insumos] != [(i['id'], i['stock'], i['costo_unidad']) for i in q.fetchall()]:
            raise ValueError('La migración alteró inventario o costos')
        return informe


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    # Sin cargar .env implícitamente: elegir el destino explícitamente.
    conn = psycopg2.connect(os.environ['MIGRATION_DATABASE_URL'])
    conn.set_session(readonly=not args.apply)
    try:
        result = migrar(conn, args.apply)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
        print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
