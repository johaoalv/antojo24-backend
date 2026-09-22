# Runbook: cierre mensual

## Objetivo

Cerrar el mes con una lectura clara de ventas, gastos, utilidad, rentabilidad y tesorería, sin mezclar movimientos pagados con Fondos.

## Antes de cerrar

1. Confirmar que las ventas y los gastos del último día ya aparezcan en el Dashboard.
2. Revisar los pedidos pendientes y resolverlos o documentarlos.
3. Revisar compras, mermas y gastos extraordinarios del mes.
4. Verificar el Libro de Caja por sucursal y la Tesorería por separado.
5. Confirmar el método de pago de cada gasto; los pagos con Fondos no forman parte de la rentabilidad mensual.

## Cifras a registrar

- Periodo y sucursal.
- Ingresos mostrados en el Dashboard.
- Gastos mostrados en el Dashboard.
- Utilidad neta y rentabilidad.
- Gastos extraordinarios del mes, separados de los gastos habituales.
- Saldo de caja por Yappy y efectivo.
- Movimientos de Fondos / Tesorería.

## Cálculos

```text
Utilidad neta = ingresos - gastos
Rentabilidad (%) = (utilidad neta / ingresos) × 100
```

Mantener los gastos con Fondos fuera de esta fórmula y reportarlos como impacto sobre tesorería.

## Validaciones

- Los importes de ingresos, gastos y utilidad deben cuadrar: ingresos menos gastos equivale a utilidad neta.
- La rentabilidad debe coincidir con utilidad neta dividida entre ingresos.
- Todo gasto extraordinario debe tener descripción, fecha, monto y método de pago.
- Si hay diferencias entre el Dashboard y una consulta directa a la base de datos, usar el Dashboard para el reporte operativo y abrir una investigación técnica aparte.

## Registro del cierre

Crear una nota mensual con:

- Resultado final y comparación contra el mes anterior.
- Compras o pagos no recurrentes que afectaron el margen.
- Riesgos y decisiones para el mes siguiente.
- Pendientes contables o de conciliación.

## Entregable recomendado

Guardar cada cierre con un nombre como `cierre-AAAA-MM.md` dentro de `docs/operacion/cierres/`, sin incluir credenciales, datos personales ni enlaces de conexión.
