"""Pruebas contra PostgreSQL temporal. MATERIAL_TEST_DATABASE_URL debe ser local."""
import os
import unittest
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4
import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine, text

URL = os.environ.get('MATERIAL_TEST_DATABASE_URL')
os.environ.setdefault('DATABASE_PUBLIC_URL', URL or 'postgresql://localhost/test')
from scripts.migrate_materiales import migrar, planificar
from utils.consumos import CatalogoConsumos

SCHEMA = '''
CREATE TABLE insumos (id integer PRIMARY KEY,nombre text,stock numeric,costo_unidad numeric,unidad_medida text);
CREATE TABLE productos (id integer PRIMARY KEY,nombre text,precio numeric,precio_delivery numeric,es_combo boolean,combo_items jsonb,disponible boolean DEFAULT true);
CREATE TABLE recetas (id serial PRIMARY KEY,producto text,insumo_id integer REFERENCES insumos(id),cantidad_requerida numeric);
CREATE TABLE pedidos (pedido_id uuid PRIMARY KEY,total_pedido numeric,metodo_pago text,sucursal_id text,fecha date,monto_recibido numeric,monto_vuelto numeric,costo_total numeric,tipo_pedido text,estado_pago text);
CREATE TABLE productos_pedido (id serial PRIMARY KEY,pedido_id uuid REFERENCES pedidos(pedido_id),producto text,cantidad numeric,total_item numeric,metodo_pago text,sucursal_id text,fecha timestamp,costo_unitario numeric,producto_id integer);
CREATE TABLE movimientos_caja (id serial PRIMARY KEY,fecha timestamp,tipo text,categoria text,monto numeric,descripcion text,sucursal_id text,referencia_id text,metodo_pago text);
INSERT INTO insumos VALUES
 (501,'pan',100,0.4,'unidad'),(502,'carne',100,0.8,'unidad'),(503,'papas',100,0.5,'unidad'),(504,'ketchup',1000,0.0034,'ml'),(505,'soda',100,0.6,'unidad'),
 (801,'bolsa de entrega ',100,0.13,'unidad'),(802,'papel antigrasa',100,0.03,'unidad'),(803,'servilletas',100,0.004,'unidad'),
 (804,'caja de papas',100,0.033,'unidad'),(805,'envase de salsas',100,0.011,'unidad'),(806,'tapa de salsas',100,0.011,'unidad');
INSERT INTO productos VALUES
 (91,'hamburguesa',3,4,false,'[]',true),(92,'papas fritas',1,2,false,'[]',true),(93,'soda',1,1.5,false,'[]',true),
 (94,'combo 1',5,7.75,true,'[{"id":91,"cantidad":1},{"id":92,"cantidad":1},{"id":93,"cantidad":1}]',true),
 (95,'topping',0.5,0.5,false,'[]',true);
INSERT INTO recetas(producto,insumo_id,cantidad_requerida) VALUES
 ('hamburguesa',501,1),('hamburguesa',502,1),('hamburguesa',802,1),('hamburguesa',803,1),
 ('papas fritas',503,1),('papas fritas',504,20),('papas fritas',804,1),('papas fritas',805,1),('papas fritas',806,1),
 ('soda',505,1),('topping',504,20),('topping',805,1),('topping',806,1),('combo 1',801,1);
'''


@unittest.skipUnless(URL, 'Requiere PostgreSQL temporal local')
class MaterialesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from urllib.parse import urlparse
        if urlparse(URL).hostname not in ('localhost','127.0.0.1'):
            raise RuntimeError('Las pruebas solo admiten una base local desechable')
        cls.pg = psycopg2.connect(URL)
        cls.pg.set_client_encoding("UTF8")
        cls.pg.autocommit = True
        cls.engine = create_engine(URL, connect_args={'options': '-c search_path=test_materiales', 'client_encoding': 'utf8'})
        from flask import Flask
        import routes.pedido as modulo
        from routes.materiales import materiales_bp
        from routes.recetas import recetas_bp
        from routes.costeo import costeo_bp
        cls.modulo = modulo
        cls.app = Flask(__name__)
        for bp in (modulo.pedido_bp, materiales_bp, recetas_bp, costeo_bp): cls.app.register_blueprint(bp)
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose();cls.pg.close()

    def setUp(self):
        self.pg.rollback(); self.pg.autocommit = True
        with self.pg.cursor() as q:
            q.execute('DROP SCHEMA IF EXISTS test_materiales CASCADE; CREATE SCHEMA test_materiales; SET search_path=test_materiales;')
            q.execute(SCHEMA)
        self.pg.autocommit = False
        migrar(self.pg, apply=True);self.pg.commit();self.pg.autocommit=True
        self.patches = [patch('routes.pedido.engine', self.engine),patch('routes.materiales.engine', self.engine),patch('db.engine', self.engine),patch('routes.pedido.emitir_dashboard_update'),patch('routes.pedido.emitir_stock_alerts')]
        for p in self.patches:p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])

    def sql(self, sql, params=None):
        with self.engine.begin() as c:
            r=c.execute(text(sql),params or {})
            return r.mappings().all() if r.returns_rows else []

    def payload(self, **updates):
        body=dict(pedido_id=str(uuid4()),pedido=[dict(producto='combo 1',cantidad=2,total_item=15.5)],total_pedido=15.5,metodo_pago='yappy',sucursal_id='prueba',fecha='2026-09-27')
        body.update(updates);return body

    def test_migracion_ids_y_repeticion(self):
        self.assertEqual(self.sql("SELECT id FROM insumos WHERE codigo='bolsa_entrega'")[0]['id'],801)
        self.assertTrue(all(r['stock']==100 for r in self.sql("SELECT stock FROM insumos WHERE tipo='material'")))
        self.assertEqual(self.sql("SELECT count(*) AS n FROM recetas r JOIN insumos i ON i.id=r.insumo_id WHERE i.tipo='material'")[0]['n'],0)
        self.pg.autocommit=False
        self.assertIn('ya aplicada',migrar(self.pg,True)['estado']);self.pg.rollback();self.pg.autocommit=True

    def test_dos_combos_una_bolsa_y_costos(self):
        b=self.payload();r=self.client.post('/api/pedido',json=b);self.assertEqual(r.status_code,201,r.json)
        rows={r['insumo_id']:r for r in self.sql('SELECT * FROM pedido_consumos')}
        self.assertEqual(rows[801]['cantidad'],1)
        for i in (802,803,804,805,806): self.assertEqual(rows[i]['cantidad'],2)
        self.assertEqual(rows[504]['cantidad'],40)
        costo=self.sql('SELECT costo_total FROM pedidos')[0]['costo_total']
        self.assertEqual(costo,sum(r['cantidad']*r['costo_unitario'] for r in rows.values()))
        unitario=self.sql('SELECT costo_unitario FROM productos_pedido')[0]['costo_unitario']
        self.assertEqual(costo,unitario*2+Decimal('.13'))
        self.assertEqual(self.client.post('/api/pedido',json=b).status_code,409)
        self.assertEqual(self.sql('SELECT stock FROM insumos WHERE id=801')[0]['stock'],99)

    def test_cancelacion_con_receta_y_costo_modificados(self):
        b=self.payload(bolsas=3);self.assertEqual(self.client.post('/api/pedido',json=b).status_code,201)
        self.sql('UPDATE recetas SET cantidad_requerida=99');self.sql('UPDATE insumos SET costo_unidad=9')
        self.assertEqual(self.client.delete('/api/pedido/'+b['pedido_id']).status_code,200)
        self.assertEqual(self.sql('SELECT stock FROM insumos WHERE id=801')[0]['stock'],100)
        self.assertEqual(self.sql('SELECT stock FROM insumos WHERE id=504')[0]['stock'],1000)
        self.assertEqual(self.client.delete('/api/pedido/'+b['pedido_id']).status_code,404)

    def test_papas_solas_y_topping_extra(self):
        b=self.payload(pedido=[dict(producto='papas fritas',cantidad=1,total_item=2),dict(producto='topping',cantidad=1,total_item=.5)],bolsas=0)
        self.assertEqual(self.client.post('/api/pedido',json=b).status_code,201)
        rows={r['insumo_id']:r['cantidad'] for r in self.sql('SELECT * FROM pedido_consumos')}
        self.assertNotIn(803,rows);self.assertNotIn(801,rows);self.assertEqual(rows[805],2);self.assertEqual(rows[504],40)

    def test_stock_insuficiente_revierte_todo(self):
        self.sql('UPDATE insumos SET stock=0 WHERE id=806')
        r=self.client.post('/api/pedido',json=self.payload());self.assertEqual(r.status_code,400,r.json)
        self.assertEqual(len(self.sql('SELECT * FROM pedidos')),0)
        self.assertEqual(len(self.sql('SELECT * FROM movimientos_caja')),0)
        self.assertEqual(self.sql('SELECT stock FROM insumos WHERE id=501')[0]['stock'],100)

    def test_cantidades_invalidas(self):
        for n in (-1,1.5,'NaN',True,None):
            self.assertEqual(self.client.post('/api/pedido',json=self.payload(bolsas=n)).status_code,400)

    def test_publico_sin_materiales_y_costeo(self):
        r=self.client.get('/api/public/ingredientes');self.assertEqual(r.status_code,200)
        nombres={i['nombre_insumo'] for i in r.json['combo 1']}
        self.assertEqual(nombres,{'pan','carne','papas','ketchup','soda'})
        r=self.client.get('/api/costeo/productos');self.assertEqual(r.status_code,200,r.json)
        combo=next(p for p in r.json if p['producto']=='combo 1')
        self.assertEqual(len(combo['materiales']),5)
        self.assertNotIn('bolsa de entrega ',{m['nombre_insumo'] for m in combo['materiales']})
        self.assertEqual(Decimal(combo['costo_total']),Decimal(combo['costo_ingredientes'])+Decimal(combo['costo_materiales']))

    def test_material_en_receta_rechazado(self):
        r=self.client.post('/api/recetas',json=dict(producto='hamburguesa',insumo_id=802,cantidad_requerida=1))
        self.assertEqual(r.status_code,400)

    def test_configuracion_bolsa_y_asignacion(self):
        self.assertEqual(self.client.put('/api/materiales/pedido/bolsas',json={'cantidad':2}).status_code,200)
        self.assertEqual(self.client.post('/api/pedido',json=self.payload()).status_code,201)
        self.assertEqual(self.sql('SELECT cantidad FROM pedido_consumos WHERE insumo_id=801')[0]['cantidad'],2)
        self.assertEqual(self.client.put('/api/materiales/productos/91/801',json={'cantidad':1}).status_code,400)
        self.assertEqual(self.client.put('/api/materiales/productos/94/802',json={'cantidad':1}).status_code,400)

    def test_legacy_conserva_materiales_archivados(self):
        pid=str(uuid4())
        self.sql('INSERT INTO pedidos(pedido_id) VALUES (:id)',{'id':pid})
        self.sql("INSERT INTO productos_pedido(pedido_id,producto,cantidad) VALUES (:id,'hamburguesa',1)",{'id':pid})
        self.sql('UPDATE insumos SET stock=stock-1 WHERE id IN (501,502,802,803)')
        r=self.client.delete('/api/pedido/'+pid);self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(self.sql('SELECT stock FROM insumos WHERE id=803')[0]['stock'],100)
        self.assertEqual(self.sql('SELECT stock FROM insumos WHERE id=801')[0]['stock'],100)

    def test_preview_sin_cambios_y_material_faltante(self):
        self.engine.dispose()
        with self.pg.cursor() as q:
            q.execute('DROP SCHEMA test_materiales CASCADE; CREATE SCHEMA test_materiales; SET search_path=test_materiales;')
            q.execute(SCHEMA)
        self.pg.autocommit=False
        self.pg.set_session(readonly=True)
        informe=migrar(self.pg)
        self.assertIn('preview', informe['estado'])
        self.pg.rollback();self.pg.set_session(readonly=False);self.pg.autocommit=True
        with self.pg.cursor() as q:
            q.execute("SELECT to_regclass('producto_materiales')")
            self.assertIsNone(q.fetchone()[0])
            q.execute("UPDATE insumos SET nombre='sin identificar' WHERE id=802")
        self.pg.autocommit=False
        with self.assertRaisesRegex(ValueError,'papel_antigrasa'):
            migrar(self.pg,True)
        self.pg.rollback();self.pg.autocommit=True
        with self.pg.cursor() as q:
            q.execute("SELECT to_regclass('producto_materiales')")
            self.assertIsNone(q.fetchone()[0])

    def test_combo_circular_o_componente_eliminado(self):
        self.sql("UPDATE productos SET combo_items=CAST(:items AS jsonb) WHERE id=94", {"items": '[{"id":94,"cantidad":1}]'})
        r=self.client.post('/api/pedido',json=self.payload())
        self.assertEqual(r.status_code,400)
        self.assertEqual(len(self.sql('SELECT * FROM pedidos')),0)
        self.sql("UPDATE productos SET combo_items=CAST(:items AS jsonb) WHERE id=94", {"items": '[{"id":999,"cantidad":1}]'})
        self.assertEqual(self.client.post('/api/pedido',json=self.payload()).status_code,400)

    def test_ventas_concurrentes_no_sobrevenden(self):
        from concurrent.futures import ThreadPoolExecutor
        self.sql('UPDATE insumos SET stock=1 WHERE id=801')
        def vender(_):
            with self.app.test_client() as client:
                return client.post('/api/pedido',json=self.payload()).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(vender,range(2)))
        self.assertEqual(statuses.count(201),1,statuses)
        self.assertTrue(all(s in (201,400,409) for s in statuses),statuses)
        self.assertEqual(self.sql('SELECT stock FROM insumos WHERE id=801')[0]['stock'],0)
        self.assertEqual(len(self.sql('SELECT * FROM pedidos')),1)


if __name__=='__main__': unittest.main()
