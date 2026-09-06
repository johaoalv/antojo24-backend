# Playbook: rentabilidad y flujo de caja

## Fuente de verdad

Para cálculos operativos, usar los valores que muestra el **Dashboard de administración**. La consulta directa a la base de datos puede incluir pedidos pendientes o movimientos aún no reflejados por el Dashboard.

## Alcance de las métricas

- **Flujo Caja del Mes:** parte de $100, divididos en $50 de Yappy y $50 de efectivo, y registra las entradas y salidas reales.
- **Rentabilidad:** muestra ingresos, gastos, utilidad neta y porcentaje de rentabilidad.
- **Fondos / Tesorería:** los movimientos pagados con Fondos no deben incluirse en flujo de caja mensual ni en rentabilidad. Se revisan por separado en tesorería.

## Fórmulas

```text
Utilidad neta = ingresos - gastos
Rentabilidad (%) = (utilidad neta / ingresos) × 100
```

Para una proyección:

```text
Ventas proyectadas = ventas acumuladas + (promedio diario de ventas × días restantes)
Gastos proyectados = gastos acumulados + (promedio diario de gastos × días restantes)
Utilidad antes de compromisos = ventas proyectadas - gastos proyectados
Utilidad final = utilidad antes de compromisos - pagos y compras extraordinarias
Rentabilidad final = (utilidad final / ventas proyectadas) × 100
```

## Ejemplo: septiembre de 2026

Datos del Dashboard al 6 de septiembre:

- Ingresos: $262.15
- Gastos: $122.52
- Utilidad neta: $139.63
- Rentabilidad: 53.3%

Promedio de los primeros cinco días con ventas:

- Ventas diarias: $52.43
- Gastos diarios: $24.50

Proyección al viernes 11 de septiembre:

- Ingresos proyectados: $524.30
- Gastos proyectados antes de nuevos compromisos: $245.04
- Utilidad antes de compromisos: $279.26

Escenario con pago de reemplazo de $150 y compra adicional de $40:

- Utilidad neta proyectada: $89.26
- Rentabilidad proyectada: 17.0%

## Checklist rápido

1. Confirmar fecha de corte y fecha objetivo.
2. Copiar ingresos y gastos del Dashboard.
3. Calcular el promedio usando solo días de operación completos.
4. Restar pagos o compras extraordinarias por separado.
5. Comunicar utilidad antes y después de esos compromisos.
