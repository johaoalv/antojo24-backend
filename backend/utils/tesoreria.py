"""Saldos operativos continuos y traspasos internos a fondos."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from sqlalchemy import text

CENTAVO = Decimal('0.01')


def ahora_panama():
    return datetime.now(ZoneInfo('America/Panama')).replace(tzinfo=None)


def dinero(valor):
    if isinstance(valor, bool) or valor is None:
        raise ValueError('Monto inválido')
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite() or abs(numero) >= Decimal('10000000000000000') or numero != numero.quantize(CENTAVO):
            raise ValueError('Use un monto válido con hasta dos decimales')
        return numero.quantize(CENTAVO)
    except (InvalidOperation, TypeError):
        raise ValueError('Monto inválido') from None


def saldos_operativos(conn, sucursal_id=None, antes_de=None):
    """Una apertura por sucursal; nunca se reinicia al cambiar de mes.

    Para consultar días anteriores a la activación se conserva el cálculo histórico.
    """
    aperturas = conn.execute(text('SELECT * FROM tesoreria_aperturas' +
        (' WHERE sucursal_id=:s' if sucursal_id else '')), {'s': sucursal_id}).mappings().all()
    saldos = dict(yappy=Decimal(0), efectivo=Decimal(0))
    for apertura in aperturas:
        inicio = apertura['fecha_inicio']
        historico = antes_de is not None and antes_de.date() < inicio
        if historico:
            inicio = antes_de.date().replace(day=1)
        flujos = conn.execute(text('''
            SELECT metodo_pago, SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) AS saldo
            FROM movimientos_caja WHERE sucursal_id=:s AND fecha >= :inicio
            AND metodo_pago IN ('yappy','efectivo')
        ''' + (' AND fecha < :hasta' if antes_de is not None else '') +
            ' GROUP BY metodo_pago'), dict(s=apertura['sucursal_id'], inicio=inicio, hasta=antes_de)).mappings()
        for metodo in saldos:
            saldos[metodo] += Decimal('50') if historico else apertura[metodo]
        for flujo in flujos:
            saldos[flujo['metodo_pago']] += flujo['saldo'] or Decimal(0)
    if sucursal_id and not aperturas:
        raise ValueError('Esta sucursal no tiene apertura de Tesorería configurada')
    return {k: v.quantize(CENTAVO) for k, v in saldos.items()}


def historial_traspasos(conn, sucursal_id=None):
    return [dict(r) for r in conn.execute(text('''
        SELECT id::text, sucursal_id, fecha::text, yappy, efectivo,
               conservar_yappy, conservar_efectivo, yappy + efectivo AS total
        FROM tesoreria_traspasos
    ''' + (' WHERE sucursal_id=:s' if sucursal_id else '') +
        ' ORDER BY fecha DESC, id DESC LIMIT 50'), {'s': sucursal_id}).mappings()]


def registrar_traspaso(conn, identificador, sucursal_id, conservar, esperados):
    # También bloquea ventas/gastos concurrentes durante la validación de saldos.
    # Es breve y serializa dos confirmaciones, incluidas las de sucursales distintas.
    conn.execute(text("SET LOCAL lock_timeout = '5s'"))
    conn.execute(text('LOCK TABLE movimientos_caja IN SHARE ROW EXCLUSIVE MODE'))
    conn.execute(text('LOCK TABLE tesoreria_traspasos IN SHARE ROW EXCLUSIVE MODE'))
    previo = conn.execute(text('SELECT * FROM tesoreria_traspasos WHERE id=:id'), {'id': identificador}).mappings().first()
    if previo:
        if previo['sucursal_id'] != sucursal_id or any(previo['conservar_' + m] != conservar[m] for m in conservar):
            raise ValueError('El identificador ya corresponde a otro traspaso')
        return False
    saldos = saldos_operativos(conn, sucursal_id)
    if saldos != esperados:
        raise SaldoCambio('Los saldos cambiaron. Revisa los montos antes de confirmar nuevamente.')
    for metodo, saldo in saldos.items():
        restante = conservar[metodo]
        if (saldo >= 0 and not Decimal(0) <= restante <= saldo) or (saldo < 0 and restante != saldo):
            raise ValueError('El saldo a conservar debe estar entre cero y el disponible; un saldo negativo debe conservarse completo')
    montos = {m: saldos[m] - conservar[m] for m in saldos}
    total = sum(montos.values())
    if total <= 0:
        raise ValueError('El traspaso debe ser mayor que cero')
    fecha = ahora_panama()
    conn.execute(text('''INSERT INTO tesoreria_traspasos
        (id,sucursal_id,fecha,conservar_yappy,conservar_efectivo,yappy,efectivo)
        VALUES (:id,:s,:fecha,:cy,:ce,:y,:e)'''),
        dict(id=identificador, s=sucursal_id, fecha=fecha, cy=conservar['yappy'],
             ce=conservar['efectivo'], y=montos['yappy'], e=montos['efectivo']))
    for metodo, monto in [*montos.items(), ('fondos', total)]:
        if not monto:
            continue
        conn.execute(text('''INSERT INTO movimientos_caja
            (fecha,tipo,categoria,monto,descripcion,sucursal_id,referencia_id,metodo_pago)
            VALUES (:fecha,:tipo,'traspaso',:monto,:descripcion,:s,:id,:metodo)'''),
            dict(fecha=fecha, tipo='entrada' if metodo == 'fondos' else 'salida', monto=monto,
                 descripcion=('Traspaso a Fondos Antojo24 desde ' + metodo) if metodo != 'fondos'
                 else 'Traspaso recibido en Fondos Antojo24', s=sucursal_id, id=identificador, metodo=metodo))
    return True


class SaldoCambio(ValueError):
    pass
