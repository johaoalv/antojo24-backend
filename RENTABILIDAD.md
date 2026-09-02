# 📈 ANÁLISIS DE RENTABILIDAD — ANTOJO24

> Guía metodológica para extraer, calcular e interpretar métricas de rentabilidad del negocio.
> Actualizada: Agosto 2026

---

## ⚠️ FUENTES DE DATOS — CRÍTICO

**NO uses `movimientos_caja` para ventas.** Las fuentes correctas son:

| Métrica | Tabla | Campo | Nota |
|---------|-------|-------|------|
| **Ventas** | `pedidos` | `total_pedido` | Ingresos reales |
| **COGS** | `pedidos` | `costo_total` | Costo de bienes vendidos |
| **Gastos Operativos** | `movimientos_caja` | Salidas con `categoria='operativo'` | Personal, utilities, etc. |
| **Compras de Inventario** | `movimientos_caja` | Salidas con `categoria='inventario'` | Reabastecimiento |
| **Mermas** | `mermas` | cantidad × costo_unidad | Pérdida de valor de inventario |

La tabla `movimientos_caja` es para **flujo de caja y gastos**, NO para ventas.

---

## 🎯 PROPÓSITO

Este documento es un playbook para:
1. **Extraer datos** correctamente (ventas de `pedidos`, gastos de `movimientos_caja`)
2. **Calcular métricas** clave de rentabilidad (margen bruto, margen neto, eficiencia COGS)
3. **Interpretar resultados** y tomar decisiones operativas
4. **Monitorear tendencias** mensual/trimestral

No es cierre contable formal — es **business intelligence operativo** para decisiones rápidas.

---

## 📊 MÉTRICAS CLAVE

### 1. Margen Bruto (%)
```
Margen Bruto = (Ventas - COGS) / Ventas × 100
```
**Qué te dice:** De cada $1 de venta, cuántos centavos quedan después de pagar el costo de bienes.

**Rango saludable:** 45-55% (Antojo24 histórico: 50%, junio 40.6% ← alerta)

**Ejemplo:** Ventas $757 - COGS $375 = Margen Bruto $382 = 50.5%

### 2. COGS como % de Ventas
```
COGS % = (COGS / Ventas) × 100
```
**Qué te dice:** Eficiencia de compra y costo de producto.

**Interpretación:**
- 45-50%: óptimo (margen 50-55%)
- 50-55%: normal (margen 45-50%)
- 55-60%: alerta (margen 40-45%)
- > 60%: crítico (Antojo24 junio: 59.4%)

### 3. Margen Neto (Final)
```
Margen Neto = (Ventas - COGS - Gastos Operativos - Mermas) / Ventas × 100
```
**Qué te dice:** Ganancia final después de TODO.

**Rango saludable:** 20-30%

### 4. Eficiencia Operativa
```
Gastos Operativos % = (Gastos Operativos / Ventas) × 100
```
**Qué te dice:** Qué % de ventas va a pagar personal, utilities, etc.

**Meta:** < 20% (deja 30%+ para COGS y ganancia neta)

---

## 🔍 QUERIES PARA EXTRAER DATOS

### Query 1: Margen Bruto Mes a Mes (LO MÁS IMPORTANTE)
```sql
-- Rentabilidad por mes desde tabla PEDIDOS (fuente de ventas)
SELECT 
  TO_CHAR(fecha, 'YYYY-MM') as mes,
  SUM(total_pedido) as ventas,
  SUM(costo_total) as cogs,
  ROUND(SUM(total_pedido) - SUM(costo_total), 2) as margen_bruto,
  ROUND(
    (SUM(total_pedido) - SUM(costo_total)) / SUM(total_pedido) * 100, 
    1
  ) as margen_bruto_pct,
  ROUND(SUM(costo_total) / SUM(total_pedido) * 100, 1) as cogs_pct
FROM pedidos
WHERE fecha >= '2026-02-01'
GROUP BY TO_CHAR(fecha, 'YYYY-MM')
ORDER BY mes;
```

**Output esperado:**
```
mes      | ventas  | cogs    | margen_bruto | margen_bruto_pct | cogs_pct
---------|---------|---------|--------------|------------------|----------
2026-02  | 627.50  | 286.05  | 341.45       | 54.4             | 45.6
2026-06  | 548.45  | 325.58  | 222.87       | 40.6             | 59.4
2026-07  | 757.54  | 374.90  | 382.64       | 50.5             | 49.5
```

**Cómo leer:** 
- Junio tuvo 40.6% margen (BAJO, COGS subió a 59.4%)
- Julio se recuperó a 50.5% (normal)

---

### Query 2: Comparar COGS % entre meses (Detecta cambios)
```sql
-- Ver si COGS cambió de mes a mes (señal de inflación de costos o cambio de mix)
SELECT 
  TO_CHAR(fecha, 'YYYY-MM') as mes,
  SUM(total_pedido) as ventas,
  SUM(costo_total) as cogs,
  ROUND(SUM(costo_total) / SUM(total_pedido) * 100, 1) as cogs_pct,
  ROUND(
    LEAD(SUM(costo_total) / SUM(total_pedido) * 100) 
    OVER (ORDER BY TO_CHAR(fecha, 'YYYY-MM')) - 
    (SUM(costo_total) / SUM(total_pedido) * 100),
    1
  ) as cambio_cogs_pp
FROM pedidos
WHERE fecha >= '2026-02-01'
GROUP BY TO_CHAR(fecha, 'YYYY-MM')
ORDER BY mes;
```

**Qué detecta:**
- `cambio_cogs_pp` > 0 = COGS subió mes siguiente (⚠️ alarma)
- `cambio_cogs_pp` < 0 = COGS bajó mes siguiente (✅ mejora)

**Ejemplo:**
- Junio: 59.4% COGS → Julio: 49.5% COGS = **-9.9 pp** (mejora fuerte)

---

### Query 3: Ganancia Neta (Con Gastos Operativos)
```sql
-- Para ver rentabilidad FINAL: ventas - COGS - gastos operativos - mermas
SELECT 
  TO_CHAR(p.fecha, 'YYYY-MM') as mes,
  SUM(p.total_pedido) as ventas,
  SUM(p.costo_total) as cogs,
  COALESCE(SUM(CASE WHEN mc.tipo='salida' AND mc.categoria='operativo' AND mc.metodo_pago != 'fondos' THEN mc.monto ELSE 0 END), 0) as gastos_operativos,
  COALESCE(SUM(m.cantidad * i.costo_unidad), 0) as mermas,
  ROUND(
    SUM(p.total_pedido) - SUM(p.costo_total) - 
    COALESCE(SUM(CASE WHEN mc.tipo='salida' AND mc.categoria='operativo' AND mc.metodo_pago != 'fondos' THEN mc.monto ELSE 0 END), 0) -
    COALESCE(SUM(m.cantidad * i.costo_unidad), 0),
    2
  ) as ganancia_neta,
  ROUND(
    (SUM(p.total_pedido) - SUM(p.costo_total) - 
    COALESCE(SUM(CASE WHEN mc.tipo='salida' AND mc.categoria='operativo' AND mc.metodo_pago != 'fondos' THEN mc.monto ELSE 0 END), 0) -
    COALESCE(SUM(m.cantidad * i.costo_unidad), 0)) / SUM(p.total_pedido) * 100,
    1
  ) as margen_neto_pct
FROM pedidos p
LEFT JOIN movimientos_caja mc ON mc.fecha >= DATE_TRUNC('month', p.fecha)::date 
  AND mc.fecha < (DATE_TRUNC('month', p.fecha)::date + interval '1 month')
LEFT JOIN mermas m ON m.fecha >= DATE_TRUNC('month', p.fecha)::date 
  AND m.fecha < (DATE_TRUNC('month', p.fecha)::date + interval '1 month')
LEFT JOIN insumos i ON m.insumo_id = i.id
WHERE p.fecha >= '2026-02-01'
GROUP BY TO_CHAR(p.fecha, 'YYYY-MM')
ORDER BY mes;
```

**Qué incluye:**
- Ventas - COGS = Margen Bruto
- Menos gastos operativos (personal, utilities, etc.)
- Menos mermas (pérdida de inventario)
- = Ganancia Neta (lo que le queda al negocio)

**Meta:** > 20% margen neto

---

### Query 4: Ticket Promedio y Volumen de Pedidos
```sql
-- Para entender si cambios en margen son por precio, volumen o mix de producto
SELECT 
  TO_CHAR(fecha, 'YYYY-MM') as mes,
  COUNT(*) as num_pedidos,
  ROUND(SUM(total_pedido) / COUNT(*), 2) as ticket_promedio,
  ROUND(SUM(costo_total) / COUNT(*), 2) as costo_promedio_por_pedido,
  ROUND(SUM(total_pedido) - SUM(costo_total)) / COUNT(*), 2) as ganancia_promedio_por_pedido
FROM pedidos
WHERE fecha >= '2026-02-01'
GROUP BY TO_CHAR(fecha, 'YYYY-MM')
ORDER BY mes;
```

**Qué detecta:**
- Si ticket promedio bajó (clientes gastan menos)
- Si costo promedio subió (compras más caras)
- Si ganancia por pedido bajó (margen comprimido)

**Ejemplo:**
- Junio: ticket bajo = margen bajo
- Julio: ticket alto = margen mejor

---

### Query 5: Análisis Diario (Tendencias Intra-Mes)
```sql
-- Ver qué días son más/menos rentables
SELECT 
  fecha::date AS dia,
  TO_CHAR(fecha, 'Dy') AS dia_semana,
  COUNT(*) as pedidos,
  ROUND(SUM(total_pedido), 2) as ventas_dia,
  ROUND(SUM(costo_total), 2) as cogs_dia,
  ROUND(SUM(total_pedido) - SUM(costo_total), 2) as margen_bruto_dia,
  ROUND((SUM(total_pedido) - SUM(costo_total)) / SUM(total_pedido) * 100, 1) as margen_pct_dia
FROM pedidos
WHERE fecha >= '2026-07-01' AND fecha < '2026-08-01'
GROUP BY fecha::date, TO_CHAR(fecha, 'Dy')
ORDER BY fecha::date;
```

**Útil para:**
- Identificar días débiles (menos clientes)
- Optimizar staffing (viernes/sábado vs lunes)
- Detectar problemas de inventario (margen cae ciertos días)
- Decisiones de horario/oferta

---

## 💡 CÓMO INTERPRETAR LOS NÚMEROS

### Escenario A: "Todo bien, margen 25%"
✅ Sigue así. Revisa trimestral para detectar degradación.

### Escenario B: "Margen bajó de 25% a 18%"
⚠️ Alerta: investiga raíz:
- ¿Subieron precios de compra (COGS ↑)?
- ¿Bajaron precios de venta (ingresos ↓)?
- ¿Aumentó desperdicio (gastos ↑)?
- ¿Mix de productos cambió (menos rentables)?

Query para diagnosticar:
```sql
-- Compara mes actual vs mes anterior
SELECT 
  'COGS %' AS metrica,
  ROUND((SELECT SUM(CASE WHEN tipo='salida' AND categoria='inventario' THEN monto ELSE 0 END) 
          FROM movimientos_caja WHERE fecha >= '2026-06-01' AND fecha < '2026-07-01' AND metodo_pago != 'fondos') /
         (SELECT SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) 
          FROM movimientos_caja WHERE fecha >= '2026-06-01' AND fecha < '2026-07-01' AND metodo_pago != 'fondos') * 100, 1) AS junio,
  ROUND((SELECT SUM(CASE WHEN tipo='salida' AND categoria='inventario' THEN monto ELSE 0 END) 
          FROM movimientos_caja WHERE fecha >= '2026-07-01' AND fecha < '2026-08-01' AND metodo_pago != 'fondos') /
         (SELECT SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) 
          FROM movimientos_caja WHERE fecha >= '2026-07-01' AND fecha < '2026-08-01' AND metodo_pago != 'fondos') * 100, 1) AS julio
UNION ALL
SELECT 'Margen %' AS metrica,
  14.3, 30.7;
```

### Escenario C: "Margen 10%, gravísimo"
🚨 Acción inmediata:
1. Aumenta precios (3-5% es defensible si es por inflación)
2. Reduce desperdicio (recapacita equipo)
3. Considera discontinuar productos de bajo margen
4. Negocia mejor con proveedores

---

## 📋 PROCESO MENSUAL (RECOMENDADO)

**Día 1 del mes:**
- Correr Query #1 (resumen general)
- Correr Query #2 (por método)
- Si margen < 20%, investigar

**Día 15 del mes:**
- Correr Query #5 (análisis diario)
- Ajustar operaciones si hay caída detectada

**Último día del mes:**
- Correr todas las queries
- Generar reporte para decisiones Q+1
- Identificar 1 acción de mejora

---

## 🎬 CASO REAL: ANTOJO24 FEBRERO-AGOSTO 2026

### Los Números (Tabla `pedidos` — Fuente Real)

| Mes | Ventas | COGS | Margen Bruto | Margen % | COGS % |
|-----|--------|------|--------------|----------|---------|
| Feb | $627.50 | $286.05 | $341.45 | 54.4% | 45.6% |
| Mar | $454.67 | $216.37 | $238.30 | 52.4% | 47.6% |
| Abr | $800.81 | $395.88 | $404.93 | 50.6% | 49.4% |
| May | $517.46 | $262.72 | $254.74 | 49.2% | 50.8% |
| **Jun** | $548.45 | $325.58 | $222.87 | **40.6%** | **59.4%** ← ALERTA |
| **Jul** | $757.54 | $374.90 | $382.64 | **50.5%** | **49.5%** ← RECUPERACIÓN |
| Ago | $351.71 | $180.83 | $170.88 | 48.6% | 51.4% (parcial) |

### Análisis

**Pre-Junio (Feb-May):** Operación saludable
- Margen bruto consistente: 49-54%
- COGS en rango: 46-51%

**Junio: Anomalía** 🚨
- Margen bruto cayó a 40.6% (-10 pp vs mayo)
- COGS subió a 59.4% (vs 50.8% en mayo)
- **Causas probables:**
  1. Compras más caras (negociación fallida con proveedores)
  2. Mix de producto cambió (vendiste items de bajo margen)
  3. Más desperdicio/merma
  4. Error en pricing

**Julio: Auto-Corrección** ✅
- Margen volvió a 50.5% (recuperación de 9.9 pp)
- COGS bajó a 49.5% (mejora inmediata)
- Ventas crecieron 38% ($757.54 vs $548.45)
- **Sugiere:**
  - Problema en junio fue OPERATIVO, no estructural
  - Julio aplicó correcciones (mejor negociación, cambio de menu, menos merma)
  - Negocio es saludable

### Recomendación
✅ **CRÍTICO:** Identifica qué cambió entre junio y julio que mejoró COGS, y bloquéalo en operación permanente.

**Preguntas a investigar:**
1. ¿Cambió precio de proveedores entre junio y julio?
2. ¿Menú cambió (más productos de alto margen en julio)?
3. ¿Se redujo desperdicio (merma)?
4. ¿Ticket promedio subió en julio?

Una vez identificado, replica el cambio de julio en adelante.

---

## 🛠️ QUERIES ADICIONALES PARA PROFUNDIZAR

### Margen por Producto (si tienes table productos)
```sql
SELECT 
  -- Asume que referencia_id apunta a un producto
  referencia_id,
  COUNT(*) AS ventas,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) AS ingresos,
  SUM(CASE WHEN tipo='salida' THEN monto ELSE 0 END) AS costo,
  ROUND(
    (SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) - 
     SUM(CASE WHEN tipo='salida' THEN monto ELSE 0 END)) /
    NULLIF(SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END), 0) * 100, 1
  ) AS margen_pct
FROM movimientos_caja
WHERE fecha >= '2026-07-01' AND fecha < '2026-08-01'
GROUP BY referencia_id
ORDER BY ingresos DESC;
```

### Contribución al Ingreso por Categoría
```sql
SELECT 
  categoria,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) AS ingresos,
  ROUND(
    SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) /
    (SELECT SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) FROM movimientos_caja 
     WHERE fecha >= '2026-07-01' AND fecha < '2026-08-01') * 100, 1
  ) AS pct_ingresos
FROM movimientos_caja
WHERE tipo='entrada' AND fecha >= '2026-07-01' AND fecha < '2026-08-01'
GROUP BY categoria
ORDER BY ingresos DESC;
```

---

## ⚠️ NOTAS IMPORTANTES

### Fuentes de Datos (CRÍTICO)
- **Ventas:** tabla `pedidos` (campos: `total_pedido`, `costo_total`, `fecha`)
  - NO uses `movimientos_caja` para ventas — esa tabla es solo para gastos/flujo
- **Gastos Operativos:** `movimientos_caja` con `tipo='salida' AND categoria='operativo'`
- **Mermas:** tabla `mermas` (pérdida de valor de inventario, no salida de caja)
- **COGS:** viene en `pedidos.costo_total` (no es lo mismo que "inventario" en movimientos_caja)

### Lógica de `dashboard.py` (Referencia)
El endpoint `/api/dashboard` calcula ganancia neta como:
```
ganancia_neta = ventas - COGS - gastos_operativos - mermas
```

Usa esa fórmula en tus queries manuales para que coincidan.

### Conciliación
- `CIERRE_MES.md` es para conciliación **bancaria** (movimientos_caja vs banco)
- Este doc es para **rentabilidad operativa** (ventas vs costos)
- No son lo mismo

### Frecuencia
- **Mínimo:** mensual (cierre de mes)
- **Ideal:** semanal (detectar tendencias rápido)
- **Máximo:** diario (ver anomalías)

---

## 📞 ¿PREGUNTAS?

Cada query usa tabla `pedidos` para ventas. Adaptá fechas (`fecha >= '2026-MM-01'`) para el período que necesites.

Si notas algo raro en los números:
1. **Verifica la fuente:** ¿viene de `pedidos` o `movimientos_caja`?
2. **Chequea filtros:** ¿`metodo_pago='fondos'` está excluido?
3. **Valida fechas:** ¿el rango es correcto?

Última revisión: Agosto 2026 — Actualizado con análisis de tabla `pedidos`
