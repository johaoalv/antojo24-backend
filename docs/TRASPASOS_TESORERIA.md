# Traspasos manuales a Fondos Antojo24

El saldo operativo de efectivo y Yappy continúa entre meses. El cierre mensual
conserva sus cálculos y deja de implicar una transferencia de excedentes.

En Dashboard > Tesorería > Traspasar a fondos, seleccionar una sucursal e indicar
cuánto conservar en cada cuenta. Inicialmente se conserva todo. Se muestra el
importe a traspasar antes de confirmar. Puede traspasarse una sola cuenta o ambas.
El historial muestra fecha, sucursal, origen y monto; el libro de caja conserva
los asientos completos. No se permiten traspasos desde la selección Global.

Cada confirmación guarda salidas de las cuentas de origen y una entrada igual en
Fondos, con categoría `traspaso` y una referencia común. No crea gastos, ingresos
por ventas ni aportes. La Tesorería total y la utilidad se mantienen. Los gastos
pagados desde Fondos siguen funcionando como antes. El saldo de Fondos es la
Tesorería histórica menos el saldo operativo, conservando la distribución
implícita existente antes de activar esta funcionalidad.

## Activación por entorno

1. Detener el backend del entorno.
2. Configurar `MIGRATION_DATABASE_URL` explícitamente para ese destino.
3. Desde `backend`, ejecutar `env/bin/python scripts/migrate_traspasos.py`
   para revisar la vista previa y luego agregar `--apply` para activar.
4. Desplegar backend e interfaz juntos y volver a iniciar el backend.

La apertura se fija una sola vez por sucursal al primer día del mes de activación,
con los $50 de base que ya usaba el sistema. Así los saldos actuales permanecen
iguales: apertura más movimientos desde esa fecha. Esa fecha **no avanza** al
cambiar de mes. Reejecutar la migración conserva las aperturas existentes.
No se modifican movimientos, cierres o saldos históricos ni se ejecuta un traspaso
al activar. Las consultas de fechas anteriores conservan el cálculo histórico.
Al incorporar otra sucursal, configurar su apertura real en `tesoreria_aperturas`
antes de operar. No crear aperturas de $50 repetidas para una misma sucursal.

Esto es independiente de la funcionalidad de materiales revertida: no requiere
`insumos.tipo` ni modifica recetas o inventario.

## API

- `GET /api/dashboard`: agrega `saldos_operativos` y `saldo_operativo_total`.
- `GET /api/dashboard/tesoreria`: conserva `saldo_caja` y agrega `saldo_fondos`
  y `saldos_operativos`.
- `GET /api/finanzas/traspasos?sucursal_id=...`: últimos 50 traspasos.
- `POST /api/finanzas/traspasos`: `id` UUID, `sucursal_id`,
  `conservar: {yappy, efectivo}`, `saldos_esperados: {yappy, efectivo}`.
  El mismo UUID permite reintentar sin duplicar. Si cambian los saldos, devuelve
  409 y exige revisar antes de confirmar otra vez. Todos los asientos se guardan
  en una transacción; un fallo revierte todo. La confirmación bloquea brevemente
  escrituras en movimientos de caja para evitar gastar un saldo obsoleto.

## Verificación

`TRASPASOS_TEST_DATABASE_URL=postgresql://localhost/postgres env/bin/python -m unittest discover -s tests -p test_traspasos.py -v`

Usa exclusivamente un esquema temporal en PostgreSQL local. Cubre continuidad
mensual, cuentas individuales, precisión, rechazos, concurrencia, reintentos,
rollback, historial y conservación de Tesorería/utilidad.
