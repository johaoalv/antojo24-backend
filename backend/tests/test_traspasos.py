"""Pruebas reales en PostgreSQL local, con un esquema temporal aislado.

TRASPASOS_TEST_DATABASE_URL=postgresql://localhost/postgres python -m unittest discover -s tests -p test_traspasos.py -v
"""
import os
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from flask import Flask

URL = os.getenv('TRASPASOS_TEST_DATABASE_URL')


@unittest.skipUnless(URL, 'Requiere PostgreSQL local explícito')
class TraspasosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if make_url(URL).host not in (None, 'localhost', '127.0.0.1', '::1'):
            raise ValueError('Estas pruebas solo admiten PostgreSQL local')
        cls.schema = 'test_traspasos_' + uuid4().hex[:10]
        cls.admin = create_engine(URL)
        with cls.admin.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA {cls.schema}'))
        cls.engine = create_engine(URL, connect_args={'options': f'-csearch_path={cls.schema}'})
        os.environ.setdefault('DATABASE_PUBLIC_URL', URL)
        import db
        from routes import finanzas, dashboard
        from scripts.migrate_traspasos import aplicar
        cls.db_patch = patch.object(db, 'engine', cls.engine)
        cls.db_patch.start()
        cls.fin_patch = patch.object(finanzas, 'engine', cls.engine)
        cls.fin_patch.start()
        cls.dash_patch = patch.object(dashboard, 'engine', cls.engine)
        cls.dash_patch.start()
        cls.aplicar = staticmethod(aplicar)
        cls.app = Flask(__name__)
        cls.app.register_blueprint(finanzas.finanzas_bp)
        cls.app.register_blueprint(dashboard.dashboard_bp)
        cls.app.testing = True
        with cls.engine.begin() as conn:
            conn.execute(text('''CREATE TABLE tiendas_acceso (sucursal_id text, nombre_tienda text);
                CREATE TABLE movimientos_caja (id serial PRIMARY KEY, fecha timestamp, tipo text,
                categoria text, monto numeric(18,2), descripcion text, sucursal_id text,
                referencia_id text, metodo_pago text);
                CREATE TABLE pedidos (pedido_id uuid, fecha timestamp, sucursal_id text,
                total_pedido numeric, costo_total numeric);
                CREATE TABLE insumos (id integer, costo_unidad numeric);
                CREATE TABLE mermas (insumo_id integer, cantidad numeric, fecha timestamp, sucursal_id text);
            '''))
            aplicar(conn, date.today().replace(day=1))

    @classmethod
    def tearDownClass(cls):
        cls.db_patch.stop(); cls.fin_patch.stop(); cls.dash_patch.stop()
        cls.engine.dispose()
        with cls.admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {cls.schema} CASCADE'))
        cls.admin.dispose()

    def setUp(self):
        self.inicio = date.today().replace(day=1)
        self.hoy = datetime.combine(date.today(), datetime.min.time())
        self.proximo = (self.inicio + timedelta(days=32)).replace(day=1)
        with self.engine.begin() as conn:
            conn.execute(text('TRUNCATE tesoreria_traspasos,tesoreria_aperturas,movimientos_caja,tiendas_acceso CASCADE'))
            conn.execute(text("INSERT INTO tiendas_acceso VALUES ('a','A'),('b','B')"))
            self.aplicar(conn, self.inicio)
            conn.execute(text("""INSERT INTO movimientos_caja(fecha,tipo,categoria,monto,sucursal_id,metodo_pago)
                VALUES (:h,'entrada','venta',250,'a','yappy'),(:h,'entrada','venta',150,'a','efectivo'),
                (:anterior,'entrada','inversion',1000,'a','fondos')"""),
                dict(h=self.hoy, anterior=self.inicio - timedelta(days=1)))
        self.client = self.app.test_client()
        self.payload = dict(id=str(uuid4()), sucursal_id='a', saldos_esperados={'yappy':300,'efectivo':200},
                            conservar={'yappy':50,'efectivo':80})

    def saldos(self, **kwargs):
        from utils.tesoreria import saldos_operativos
        with self.engine.connect() as conn:
            return saldos_operativos(conn, 'a', **kwargs)

    def confirmar(self, payload=None):
        with patch('socket_instance.socketio.emit'):
            return self.client.post('/api/finanzas/traspasos', json=payload or self.payload)

    def test_apertura_conserva_actual_y_no_se_reinicia_el_primero(self):
        self.assertEqual(self.saldos(), {'yappy':Decimal(300),'efectivo':Decimal(200)})
        self.assertEqual(self.saldos(antes_de=datetime.combine(self.proximo, datetime.min.time())), self.saldos())
        r = self.client.get('/api/finanzas/libro-caja', query_string=dict(sucursal_id='a',fecha=self.proximo.isoformat()))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['saldo_inicial_yappy'], 300)

    def test_traspaso_cuadra_saldos_y_tesoreria_y_utilidad(self):
        antes = self.client.get('/api/dashboard?sucursal_id=a').json
        tesoreria = self.client.get('/api/dashboard/tesoreria?sucursal_id=a').json
        self.assertEqual(self.confirmar().status_code, 201)
        self.assertEqual(self.saldos(), {'yappy':Decimal(50),'efectivo':Decimal(80)})
        despues = self.client.get('/api/dashboard?sucursal_id=a').json
        for clave in ['ganancia_neta','gastos_operativos','compras_inventario','gastos_fondos','gastos_por_metodo']:
            self.assertEqual(antes['mes_actual'][clave], despues['mes_actual'][clave])
        self.assertEqual(antes['rentabilidad_mensual'], despues['rentabilidad_mensual'])
        tesoreria_despues = self.client.get('/api/dashboard/tesoreria?sucursal_id=a').json
        self.assertEqual(tesoreria['saldo_caja'], tesoreria_despues['saldo_caja'])
        self.assertEqual(tesoreria_despues['saldo_fondos'] - tesoreria['saldo_fondos'], 370)
        self.assertEqual(despues['saldo_operativo_total'], 130)
        historial = self.client.get('/api/finanzas/traspasos?sucursal_id=a').json
        self.assertEqual(len(historial), 1)
        self.assertEqual(Decimal(historial[0]['total']), Decimal(370))
        self.assertEqual(self.client.get('/api/finanzas/traspasos?sucursal_id=b').json, [])

    def test_reintento_idempotente_y_confirmacion_obsoleta(self):
        self.assertEqual(self.confirmar().status_code, 201)
        self.assertEqual(self.confirmar().status_code, 200)
        self.payload['id'] = str(uuid4())
        self.assertEqual(self.confirmar().status_code, 409)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM movimientos_caja WHERE categoria='traspaso'")).scalar(), 3)

    def test_solo_efectivo(self):
        self.payload['conservar'] = dict(yappy=300,efectivo=0)
        self.assertEqual(self.confirmar().status_code, 201)
        self.assertEqual(self.saldos(), {'yappy':Decimal(300),'efectivo':Decimal(0)})

    def test_importes_invalidos_no_dejan_movimientos(self):
        for valor in [None, True, -1, 301, 'NaN', 'Infinity', '5.123']:
            with self.subTest(valor=valor):
                self.payload['conservar']['yappy'] = valor
                self.assertEqual(self.confirmar().status_code, 400)
        self.assertEqual(self.saldos(), {'yappy':Decimal(300),'efectivo':Decimal(200)})
        self.assertEqual(self.client.get('/api/finanzas/traspasos?sucursal_id=a').json, [])

    def test_cero_y_sucursal_global_rechazados(self):
        self.payload['conservar'] = dict(yappy=300,efectivo=200)
        self.assertEqual(self.confirmar().status_code, 400)
        self.payload['sucursal_id'] = 'global'
        self.assertEqual(self.confirmar().status_code, 400)

    def test_fallo_entre_asientos_revierte_todo(self):
        with self.engine.begin() as conn:
            conn.execute(text("ALTER TABLE movimientos_caja ADD CONSTRAINT no_fondos_traspaso CHECK (NOT (categoria='traspaso' AND metodo_pago='fondos'))"))
        try:
            self.assertEqual(self.confirmar().status_code, 500)
            self.assertEqual(self.saldos(), {'yappy':Decimal(300),'efectivo':Decimal(200)})
            self.assertEqual(self.client.get('/api/finanzas/traspasos?sucursal_id=a').json, [])
        finally:
            with self.engine.begin() as conn:
                conn.execute(text('ALTER TABLE movimientos_caja DROP CONSTRAINT no_fondos_traspaso'))

    def test_migracion_repetida_no_reinicia_apertura(self):
        with self.engine.begin() as conn:
            self.aplicar(conn, self.proximo)
        self.assertEqual(self.saldos(), {'yappy':Decimal(300),'efectivo':Decimal(200)})

    def test_historia_previa_mantiene_calculo_original(self):
        previo = self.inicio - timedelta(days=1)
        self.assertEqual(self.saldos(antes_de=datetime.combine(previo,datetime.min.time())),
                         {'yappy':Decimal(50),'efectivo':Decimal(50)})

    def test_confirmaciones_concurrentes_solo_una_descuenta(self):
        from concurrent.futures import ThreadPoolExecutor
        from utils.tesoreria import registrar_traspaso, SaldoCambio
        def intento(_):
            try:
                with self.engine.begin() as conn:
                    registrar_traspaso(conn,str(uuid4()),'a', {'yappy':Decimal(50),'efectivo':Decimal(80)},
                                      {'yappy':Decimal(300),'efectivo':Decimal(200)})
                return 'ok'
            except SaldoCambio:
                return 'conflicto'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(intento,range(2))), ['ok','conflicto'])
        self.assertEqual(self.saldos(), {'yappy':Decimal(50),'efectivo':Decimal(80)})


if __name__ == '__main__':
    unittest.main()
