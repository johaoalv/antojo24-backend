"""Separa saldos acumulados, actividad del día y traspasos internos."""
from decimal import Decimal
from sqlalchemy import text
from utils.tesoreria import saldos_operativos


def calcular_resumen_cierre(conn, sucursal_id, inicio, fin):
    iniciales = saldos_operativos(conn, sucursal_id, inicio)
    movimientos = conn.execute(text('''
        SELECT tipo, metodo_pago, categoria, SUM(monto) AS total
        FROM movimientos_caja
        WHERE sucursal_id=:s AND fecha >= :inicio AND fecha < :fin
        GROUP BY tipo, metodo_pago, categoria
    '''), dict(s=sucursal_id, inicio=inicio, fin=fin)).mappings().all()
    neto, traspasos = {}, {}
    entradas = salidas = Decimal(0)
    for m in movimientos:
        metodo = m['metodo_pago'] or 'otro'
        monto = m['total'] or Decimal(0)
        signo = 1 if m['tipo'] == 'entrada' else -1
        neto[metodo] = neto.get(metodo, Decimal(0)) + signo * monto
        if m['categoria'] == 'traspaso':
            traspasos[metodo] = traspasos.get(metodo, Decimal(0)) + signo * monto
        elif signo == 1:
            entradas += monto
        else:
            salidas += monto
    finales = {m: iniciales[m] + neto.get(m, Decimal(0)) for m in iniciales}
    cantidad = conn.execute(text('''SELECT COUNT(DISTINCT pedido_id)
        FROM productos_pedido WHERE sucursal_id=:s AND fecha >= :inicio AND fecha < :fin'''),
        dict(s=sucursal_id, inicio=inicio, fin=fin)).scalar_one()
    return dict(hay_movimientos=bool(movimientos), neto=neto, entradas=entradas,
                salidas=salidas, iniciales=iniciales, finales=finales,
                traspasos=traspasos, ventas_realizadas=cantidad)
