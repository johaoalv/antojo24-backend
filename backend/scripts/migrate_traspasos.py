"""Activa saldos continuos conservando los saldos del mes de activación.

MIGRATION_DATABASE_URL debe señalar explícitamente el destino. Sin --apply solo lee.
"""
import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import os
from sqlalchemy import create_engine, text


def aplicar(conn, inicio):
    conn.execute(text(Path(__file__).resolve().parents[1].joinpath(
        'migrations/20261030_traspasos.sql').read_text()))
    conn.execute(text('''INSERT INTO tesoreria_aperturas(sucursal_id,fecha_inicio,yappy,efectivo)
        SELECT sucursal_id, :inicio, 50, 50 FROM (
            SELECT sucursal_id FROM tiendas_acceso
            UNION SELECT sucursal_id FROM movimientos_caja
        ) sucursales WHERE sucursal_id IS NOT NULL AND sucursal_id <> 'global'
        ON CONFLICT(sucursal_id) DO NOTHING'''), {'inicio': inicio})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    engine = create_engine(os.environ['MIGRATION_DATABASE_URL'])
    inicio = datetime.now(ZoneInfo('America/Panama')).date().replace(day=1)
    with engine.begin() as conn:
        if args.apply:
            aplicar(conn, inicio)
            print('Aperturas configuradas; no se modificaron movimientos ni saldos históricos.')
        else:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            rows = conn.execute(text('''SELECT sucursal_id, metodo_pago,
                50 + COALESCE(SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END),0) AS saldo
                FROM movimientos_caja WHERE fecha >= :inicio
                AND metodo_pago IN ('yappy','efectivo')
                GROUP BY sucursal_id,metodo_pago ORDER BY 1,2'''), {'inicio': inicio}).mappings()
            print('Inicio continuo propuesto:', inicio)
            for row in rows:
                print(dict(row))
            print('Vista previa; para aplicar usar --apply con el backend detenido.')
