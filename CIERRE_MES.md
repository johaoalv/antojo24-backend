# 📒 CIERRE DE MES — ANTOJO24
> Guía completa para conciliación bancaria y análisis mensual usando la base de datos.
> Actualizada: Mayo 2026

---

## 🔌 CONEXIÓN A LA BASE DE DATOS

```
postgresql://postgres:maDbUALbbAxJzhdqbIcFpvfyGwkYoRsl@crossover.proxy.rlwy.net:53971/railway
```

**Desde terminal:**
```bash
psql "postgresql://postgres:maDbUALbbAxJzhdqbIcFpvfyGwkYoRsl@crossover.proxy.rlwy.net:53971/railway"
```

---

## 🗄️ TABLA PRINCIPAL: `movimientos_caja`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | integer | PK autoincremental |
| `fecha` | timestamp | Fecha y hora del movimiento |
| `tipo` | varchar(10) | `'entrada'` o `'salida'` |
| `categoria` | varchar(50) | `venta`, `inventario`, `personal`, `ajuste`, `otro` |
| `monto` | numeric | Monto positivo siempre |
| `descripcion` | text | Descripción libre |
| `sucursal_id` | varchar(50) | Siempre usar `'sucursal_santa_maria'` |
| `metodo_pago` | varchar(20) | `'yappy'` o `'efectivo'` |
| `referencia_id` | varchar(50) | ID externo si aplica (pedido, etc.) |

> ⚠️ **IMPORTANTE:** Si no pones `sucursal_id = 'sucursal_santa_maria'`, el movimiento NO aparece en la interfaz.

---

## 🧠 CONCEPTOS CLAVE PARA CONCILIACIÓN

### Yappy Comercial vs Banco
- **Yappy Comercial** = app donde se ven las ventas del día
- **Banco** = cuenta donde llega el dinero
- Las ventas Yappy del día **X** llegan al banco el día **X+1** (T+1)
- Las liquidaciones de **PedidosYa y Uber** van **directamente al banco**, NO pasan por Yappy Comercial

### Dirección del gap
- Si **banco > sistema** → faltan entradas en el sistema O sobran salidas registradas
- Si **sistema > banco** → sobran entradas en el sistema O faltan salidas registradas

### Saldo inicial de referencia
- El saldo Yappy al inicio del análisis (14 mayo 2026) era **$150.09**
- Ajustar este valor según el mes que se trabaje consultando el último saldo del mes anterior

### 🔄 SALDO INICIAL CADA MES (IMPORTANTE)
**Cada mes arranca el 01 con saldos iniciales:**
- **Yappy:** $50.00
- **Efectivo:** $50.00

**Cálculo del saldo final de mes:**
```
Saldo final = Saldo inicial ($50) + Neto del mes (ingresos - gastos)
```

**Ejemplo (Junio 2026):**
- Yappy: $50 + ($99.00 - $75.88) = $50 + $23.12 = **$73.12**
- Efectivo: $50 + ($71.75 - $48.46) = $50 + $23.29 = **$73.29**

---

## 📊 QUERIES ESENCIALES

### 1. Resumen general del mes
```sql
SELECT 
  metodo_pago,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) AS ingresos,
  SUM(CASE WHEN tipo='salida' THEN monto ELSE 0 END) AS gastos,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) AS neto
FROM movimientos_caja
WHERE fecha >= '2026-MM-01' AND fecha < '2026-MM+1-01'
GROUP BY metodo_pago
ORDER BY ingresos DESC;
```

### 2. Totales generales del mes
> ⚠️ Excluye `metodo_pago='fondos'` — esos movimientos son compras grandes pagadas con la
> cuenta de Fondos Antojo24 (tesorería), no plata real del mes. Si se incluyen aquí, la
> utilidad neta y la conciliación bancaria del mes salen mal. Ver query #4.1 para verlos aparte.
```sql
SELECT 
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) AS total_ingresos,
  SUM(CASE WHEN tipo='salida' THEN monto ELSE 0 END) AS total_gastos,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) AS utilidad_neta
FROM movimientos_caja
WHERE fecha >= '2026-MM-01' AND fecha < '2026-MM+1-01'
  AND metodo_pago != 'fondos';
```

### 3. Balance corriente Yappy (para conciliación)
```sql
-- Cambiar 150.09 por el saldo real de inicio del período
SELECT 
  fecha::date AS dia,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) AS movimiento_dia,
  SUM(SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END)) 
    OVER (ORDER BY fecha::date) + 150.09 AS saldo_sistema
FROM movimientos_caja
WHERE metodo_pago='yappy' AND fecha >= '2026-05-14' AND fecha < '2026-06-01'
GROUP BY fecha::date
ORDER BY dia;
```

### 4. Gastos por categoría
> ⚠️ Excluye `metodo_pago='fondos'` por la misma razón que la query #2.
```sql
SELECT categoria, SUM(monto) AS total
FROM movimientos_caja
WHERE tipo='salida' AND fecha >= '2026-MM-01' AND fecha < '2026-MM+1-01'
  AND metodo_pago != 'fondos'
GROUP BY categoria
ORDER BY total DESC;
```

### 4.1 Gastos pagados con Fondos del mes (informativo, aparte de la conciliación)
```sql
SELECT fecha::date, categoria, descripcion, monto
FROM movimientos_caja
WHERE tipo='salida' AND metodo_pago='fondos'
  AND fecha >= '2026-MM-01' AND fecha < '2026-MM+1-01'
ORDER BY fecha;
```

### 5. Ventas por día de la semana
```sql
SELECT 
  TO_CHAR(fecha, 'Day') AS dia_semana,
  EXTRACT(DOW FROM fecha) AS dow,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) AS ventas,
  COUNT(CASE WHEN tipo='entrada' THEN 1 END) AS transacciones
FROM movimientos_caja
WHERE fecha >= '2026-MM-01' AND fecha < '2026-MM+1-01' AND categoria='venta'
GROUP BY dia_semana, dow
ORDER BY dow;
```

### 6. Ticket promedio por método de pago
```sql
SELECT 
  metodo_pago,
  COUNT(*) AS pedidos,
  ROUND(AVG(monto), 2) AS ticket_promedio,
  MAX(monto) AS venta_max,
  MIN(monto) AS venta_min
FROM movimientos_caja
WHERE tipo='entrada' AND categoria='venta' 
  AND fecha >= '2026-MM-01' AND fecha < '2026-MM+1-01'
GROUP BY metodo_pago;
```

### 7. Ventas por semana del mes
```sql
SELECT 
  CASE 
    WHEN EXTRACT(DAY FROM fecha) BETWEEN 1 AND 7 THEN 'Semana 1 (1-7)'
    WHEN EXTRACT(DAY FROM fecha) BETWEEN 8 AND 14 THEN 'Semana 2 (8-14)'
    WHEN EXTRACT(DAY FROM fecha) BETWEEN 15 AND 21 THEN 'Semana 3 (15-21)'
    ELSE 'Semana 4 (22-31)'
  END AS semana,
  SUM(monto) AS ventas
FROM movimientos_caja
WHERE tipo='entrada' AND categoria='venta' 
  AND fecha >= '2026-MM-01' AND fecha < '2026-MM+1-01'
GROUP BY semana
ORDER BY semana;
```

### 8. Días sin ventas
```sql
SELECT fecha::date AS dia
FROM generate_series('2026-MM-01'::date, '2026-MM-30'::date, '1 day') AS fecha
WHERE fecha::date NOT IN (
  SELECT DISTINCT fecha::date FROM movimientos_caja
  WHERE tipo='entrada' AND categoria='venta' 
    AND fecha >= '2026-MM-01' AND fecha < '2026-MM+1-01'
)
ORDER BY dia;
```

### 9. Ratio de gastos vs ingresos (últimos 3 meses)
```sql
SELECT 
  TO_CHAR(fecha, 'Mon YYYY') AS mes,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) AS ingresos,
  SUM(CASE WHEN tipo='salida' THEN monto ELSE 0 END) AS gastos,
  ROUND(SUM(CASE WHEN tipo='salida' THEN monto ELSE 0 END) / 
    NULLIF(SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END),0) * 100, 1) AS pct_gasto
FROM movimientos_caja
WHERE fecha >= '2026-MM-01' AND fecha < '2026-MM+3-01'  -- ajustar rango
GROUP BY TO_CHAR(fecha, 'Mon YYYY'), DATE_TRUNC('month', fecha)
ORDER BY DATE_TRUNC('month', fecha);
```

---

## ✅ PROCESO PASO A PASO: CIERRE DE MES

### PASO 1 — Obtener saldo bancario real y extracto del mes
1. Entrar al banco y anotar el saldo final del mes en la cuenta Yappy de Antojo24.
2. **OBLIGATORIO:** Descargar el extracto bancario del mes (.xlsx) de la cuenta operativa Yappy. Este documento es indispensable para identificar las **comisiones bancarias Yappy** (líneas `COMISION TRANSACCIONES YAPPY Antojo24`) que NO se registran automáticamente y deben sumarse al cierre.
3. Sumar todas las comisiones del mes — ese total se registra como salida en el PASO 6.

### PASO 2 — Obtener saldo sistema
```sql
SELECT ROUND(SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) + 50.00, 2) AS saldo_yappy
FROM movimientos_caja
WHERE metodo_pago='yappy' AND fecha >= '2026-06-01' AND fecha < '2026-07-01';
```
> **IMPORTANTE:** El `+ 50.00` es el saldo inicial que SIEMPRE arranca cada mes (tanto Yappy como efectivo).
> Para otros meses, cambiar las fechas pero mantener el saldo inicial en $50.00

### PASO 3 — Calcular diferencia
```
diferencia = saldo_banco - saldo_sistema
```
- Si positivo → banco tiene más → faltan entradas o sobran salidas en sistema
- Si negativo → sistema tiene más → sobran entradas o faltan salidas en sistema

### PASO 4 — Identificar discrepancias
Revisar en este orden:
1. **Gastos pagados desde cuenta personal** (no de Antojo) que se registraron como salidas Yappy
2. **Cobros con error de monto** (ej: cobrado $43.80 pero registrado $45.00)
3. **Transacciones de plataformas** (PedidosYa, Uber) — van directo al banco, no por Yappy Comercial
4. **Entradas duplicadas** o movimientos con fecha incorrecta

### PASO 5 — Insertar correcciones
```sql
-- Plantilla de entrada correctora
INSERT INTO movimientos_caja (fecha, tipo, monto, descripcion, categoria, metodo_pago, sucursal_id)
VALUES ('YYYY-MM-DD HH:MM:SS', 'entrada', MONTO, 'Descripcion del ajuste', 'ajuste', 'yappy', 'sucursal_santa_maria');

-- Plantilla de salida correctora
INSERT INTO movimientos_caja (fecha, tipo, monto, descripcion, categoria, metodo_pago, sucursal_id)
VALUES ('YYYY-MM-DD HH:MM:SS', 'salida', MONTO, 'Descripcion del ajuste', 'ajuste', 'yappy', 'sucursal_santa_maria');
```

### PASO 6 — Ajuste general de cierre

**6.1 Comisiones bancarias Yappy del mes (OBLIGATORIO):**
Tomar el total de comisiones del extracto bancario (PASO 1) e insertar como salida:
```sql
INSERT INTO movimientos_caja (fecha, tipo, monto, descripcion, categoria, metodo_pago, sucursal_id)
VALUES ('YYYY-MM-30 23:59:00', 'salida', TOTAL_COMISIONES, 'Ajuste cierre: comisiones bancarias Yappy MES YYYY', 'ajuste', 'yappy', 'sucursal_santa_maria');
```

**6.2 Diferencia residual (si aplica):**
Si queda una diferencia menor (< $2.00) de origen no identificable (redondeos, fees menores):
```sql
INSERT INTO movimientos_caja (fecha, tipo, monto, descripcion, categoria, metodo_pago, sucursal_id)
VALUES ('YYYY-MM-30 23:59:00', 'entrada', DIFERENCIA, 'Ajuste conciliacion Yappy MES YYYY', 'ajuste', 'yappy', 'sucursal_santa_maria');
```

### PASO 7 — Verificar saldo final del mes
> ⚠️ El `+ 50.00` SOLO aplica a `yappy` y `efectivo` (el saldo inicial fijo del mes). Si se
> agrupara sin filtrar, un mes con compras pagadas por `metodo_pago='fondos'` sumaría un
> `+50.00` que no le corresponde a esa cuenta.
```sql
SELECT 
  metodo_pago,
  ROUND(SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) + 50.00, 2) AS saldo_final
FROM movimientos_caja
WHERE fecha >= '2026-06-01' AND fecha < '2026-07-01'
  AND metodo_pago IN ('yappy', 'efectivo')
GROUP BY metodo_pago;
```
> El saldo final debe coincidir con lo que tienes en el libro físico.
> El `+ 50.00` es el saldo inicial de mes que siempre arranca igual.
> Para ver cuánto se gastó del fondo ese mes (sin baseline de $50), usar la query #4.1.

### PASO 8 — Generar resumen para libro físico
Usar los queries de la sección anterior para imprimir o anotar:
- Ingresos / Gastos / Utilidad neta
- Desglose por método de pago
- Desglose de gastos por categoría
- Saldo banco vs sistema (diferencia = $0.00)

---

## 🔧 ERRORES COMUNES Y SOLUCIONES

| Error | Causa | Solución |
|---|---|---|
| Movimiento no aparece en interfaz | Falta `sucursal_id` | `UPDATE movimientos_caja SET sucursal_id='sucursal_santa_maria' WHERE id=XXX` |
| Fecha incorrecta | Se insertó con fecha equivocada | `UPDATE movimientos_caja SET fecha='YYYY-MM-DD HH:MM:SS' WHERE id=XXX` |
| `invalid byte sequence for encoding UTF8` | Caracteres especiales en query | Evitar tildes/ñ en strings SQL directo desde terminal |
| Gap no cierra con lógica esperada | Dirección del gap invertida | Verificar: banco > sistema o sistema > banco antes de actuar |
| Gasto personal registrado como Yappy | Error de registro en el momento | Insertar entrada correctora (no borrar — el libro físico ya lo tiene escrito) |

---

## 📋 HISTORIAL DE AJUSTES MAYO 2026

| ID | Fecha | Tipo | Monto | Descripción | Motivo |
|---|---|---|---|---|---|
| 634 | 31/05/2026 | entrada | $1.20 | Corrección Fortunato 11/5 | Cobrado $43.80, registrado $45.00 |
| 637 | 31/05/2026 | entrada | $1.26 | Ajuste conciliación Yappy mayo 2026 | Diferencia residual (comisiones + redondeos) |

## 📋 HISTORIAL DE AJUSTES JUNIO 2026 (pendiente — programado 30/06)

| Fecha | Tipo | Monto | Descripción | Motivo |
|---|---|---|---|---|
| 30/06/2026 | salida | $12.80 | Ajuste comisiones bancarias Yappy: $2.58 junio + $10.22 acumulado feb-may | Conciliación con extracto bancario. Inaugura política de registrar comisiones cada cierre. |

---

## 📌 NOTAS PERMANENTES DEL NEGOCIO

- **Saldo inicial cada mes**: Ambos métodos (Yappy y efectivo) arrancan el 01 con **$50.00**
- **PedidosYa y Uber** liquidan directo al banco, nunca aparecen en Yappy Comercial
- **T+1**: venta Yappy de hoy llega al banco mañana
- **Sucursal única activa**: `sucursal_santa_maria`
- **Métodos de pago activos**: `yappy`, `efectivo` (plata del mes) y `fondos` (gastos pagados desde la cuenta de Fondos Antojo24 — ver nota abajo)
- **Categorías de gastos**: `inventario`, `personal`, `ajuste`, `otro`
- **Categorías de ingresos**: `venta`, `ajuste`
- Nunca borrar movimientos — siempre hacer asiento de corrección (el libro físico ya quedó escrito)
- **Comisiones bancarias Yappy**: El banco cobra una pequeña comisión por cada depósito Yappy (~$0.02–$0.42 por movimiento). NUNCA se registran automáticamente en el sistema. **OBLIGATORIO al cierre de mes:** descargar el extracto bancario, sumar todas las líneas `COMISION TRANSACCIONES YAPPY Antojo24` y registrarlas como una salida única de ajuste el último día del mes.
- **Cuenta de fondos antojo (04-72-00-821887-0)**: Cuenta de ahorros separada donde se depositan los excedentes al cierre de mes (todo lo que sobre de $50 en yappy + $50 en efectivo). La transferencia de excedentes hacia el fondo sigue siendo implícita (NO requiere asiento). Lo que **sí tiene visibilidad en el sistema (implementado agosto 2026)** es el camino inverso: cuando se compra algo grande (>$300 típicamente) pagando *desde* el fondo, ese gasto se registra en `/api/gastos` con `metodo_pago='fondos'`.
  - Se ve en el listado de Gastos y en el Libro de Caja con su propio tag, pero **no** afecta `saldo_yappy` / `saldo_efectivo` ni la utilidad/flujo de caja del mes en el dashboard.
  - Sí resta de la card "Tesorería" (saldo histórico acumulado), porque es plata real que salió del negocio.
  - Al correr las queries manuales de cierre de mes de este documento, filtrar/excluir `metodo_pago='fondos'` (ya viene indicado en cada query afectada) para no mezclarlo con la conciliación bancaria de yappy/efectivo.
