# 📈 ANÁLISIS DE RENTABILIDAD — ANTOJO24

> Guía metodológica para extraer, calcular e interpretar métricas de rentabilidad del negocio.
> Actualizada: Agosto 2026

---

## 🎯 PROPÓSITO

Este documento es un playbook para:
1. **Extraer datos** de la base de datos (`movimientos_caja`)
2. **Calcular métricas** clave de rentabilidad (margen, utilidad, ROI por canal)
3. **Interpretar resultados** y tomar decisiones operativas
4. **Monitorear tendencias** mensual/trimestral

No es cierre contable formal — es **business intelligence operativo** para decisiones rápidas.

---

## 📊 MÉTRICAS CLAVE

### 1. Utilidad Neta (Bottom Line)
```
Utilidad Neta = Ingresos Totales - Gastos Totales
```
**Qué te dice:** Plata pura que quedó en el negocio ese mes.

**Rango saludable:** 20-30% para comercio/comidas (Antojo24 está en 23.6%, bueno)

### 2. Margen de Ganancia (%)
```
Margen % = (Utilidad Neta / Ingresos Totales) × 100
```
**Qué te dice:** Por cada $1 que entra, cuántos centavos son ganancia pura.

**Interpretación:**
- < 10%: crítico, revisar precios o costos
- 10-20%: bajo, hay mejora posible
- 20-30%: sano
- > 30%: excelente (Yappy en Antojo24 está acá)

### 3. Ratio Gasto/Ingreso
```
Ratio G/I = (Gastos Totales / Ingresos Totales) × 100
```
**Qué te dice:** De cada $1 de ingreso, cuántos centavos se gastan.

**Parámetro:**
- Ratio 70% = 30% margen
- Ratio 85% = 15% margen
- Ratio 90%+ = margen de riesgo

### 4. COGS (Cost of Goods Sold) como % de Ingresos
```
COGS % = (Inventario Gasto / Ingresos Totales) × 100
```
**Qué te dice:** Eficiencia de compra.

**Rango ideal:** 60-70% (Antojo24 está en ~69%, óptimo)

---

## 🔍 QUERIES PARA EXTRAER DATOS

### Paso 1: Resumen General del Período
```sql
-- Usar para comparar mes a mes o trimestre a trimestre
SELECT 
  TO_CHAR(fecha, 'Mon YYYY') AS periodo,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) AS ingresos,
  SUM(CASE WHEN tipo='salida' THEN monto ELSE 0 END) AS gastos,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) AS utilidad_neta,
  ROUND(
    SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) / 
    NULLIF(SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END), 0) * 100, 
    1
  ) AS margen_pct
FROM movimientos_caja
WHERE fecha >= '2026-06-01' AND fecha < '2026-08-01'
  AND metodo_pago != 'fondos'
GROUP BY TO_CHAR(fecha, 'Mon YYYY'), DATE_TRUNC('month', fecha)
ORDER BY DATE_TRUNC('month', fecha);
```

**Output esperado:**
```
periodo  | ingresos | gastos | utilidad_neta | margen_pct
---------|----------|--------|---------------|----------
Jun 2026 | 528.02   | 452.53 | 75.49         | 14.3
Jul 2026 | 691.45   | 479.53 | 211.92        | 30.7
```

---

### Paso 2: Rentabilidad por Método de Pago
```sql
-- Usa para entender qué canal es más rentable
SELECT 
  metodo_pago,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) AS ingresos,
  SUM(CASE WHEN tipo='salida' THEN monto ELSE 0 END) AS gastos,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) AS neto,
  ROUND(
    SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) / 
    NULLIF(SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END), 0) * 100, 
    1
  ) AS margen_pct,
  ROUND(
    SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) / 
    (SELECT SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) FROM movimientos_caja 
     WHERE fecha >= '2026-06-01' AND fecha < '2026-08-01' AND metodo_pago != 'fondos') * 100,
    1
  ) AS pct_ingresos_totales
FROM movimientos_caja
WHERE fecha >= '2026-06-01' AND fecha < '2026-08-01'
  AND metodo_pago != 'fondos'
GROUP BY metodo_pago
ORDER BY ingresos DESC;
```

**Output esperado:**
```
metodo_pago | ingresos | gastos | neto   | margen_pct | pct_ingresos_totales
------------|----------|--------|--------|------------|--------------------
yappy       | 857.71   | 601.27 | 256.44 | 29.9       | 70.3
efectivo    | 361.76   | 330.79 | 30.97  | 8.6        | 29.7
```

**Interpretación:**
- Yappy: motor principal, margen sano (29.9%)
- Efectivo: riesgoso (8.6%), considerar optimizar o aumentar precios

---

### Paso 3: Desglose de Gastos por Categoría
```sql
-- Usa para identificar dónde se va la plata
SELECT 
  categoria,
  SUM(monto) AS total,
  COUNT(*) AS transacciones,
  ROUND(AVG(monto), 2) AS promedio_por_transaccion,
  ROUND(
    SUM(monto) / (SELECT SUM(CASE WHEN tipo='salida' THEN monto ELSE 0 END) 
                   FROM movimientos_caja WHERE fecha >= '2026-06-01' AND fecha < '2026-08-01' 
                   AND metodo_pago != 'fondos') * 100, 
    1
  ) AS pct_gastos_totales
FROM movimientos_caja
WHERE tipo='salida' 
  AND fecha >= '2026-06-01' AND fecha < '2026-08-01'
  AND metodo_pago != 'fondos'
GROUP BY categoria
ORDER BY total DESC;
```

**Output esperado:**
```
categoria  | total   | transacciones | promedio | pct_gastos_totales
-----------|---------|---------------|----------|-------------------
inventario | 841.21  | 47            | 17.89    | 90.3
personal   | 40.13   | 16            | 2.51     | 4.3
operativo  | 27.17   | 3             | 9.06     | 2.9
ajuste     | 15.55   | 2             | 7.78     | 1.7
publicidad | 5.00    | 1             | 5.00     | 0.5
otro       | 3.00    | 2             | 1.50     | 0.3
```

**Interpretación:**
- Inventario domina (90.3%) — es el costo de bienes vendidos, controlable
- Personal está en línea (4.3%)
- Oportunidad: personal + operativo + ajuste suman solo 4.6%, hay margen para crecer sin aumentar gastos fijos

---

### Paso 4: COGS Analysis (Inventario vs Ingresos)
```sql
-- Usa para medir eficiencia de compra
SELECT 
  TO_CHAR(fecha, 'Mon YYYY') AS periodo,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) AS ingresos,
  SUM(CASE WHEN tipo='salida' AND categoria='inventario' THEN monto ELSE 0 END) AS cogs,
  ROUND(
    SUM(CASE WHEN tipo='salida' AND categoria='inventario' THEN monto ELSE 0 END) / 
    NULLIF(SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END), 0) * 100, 
    1
  ) AS cogs_pct,
  ROUND(
    (SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) - 
     SUM(CASE WHEN tipo='salida' AND categoria='inventario' THEN monto ELSE 0 END)) /
    NULLIF(SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END), 0) * 100,
    1
  ) AS margen_sin_cogs_pct
FROM movimientos_caja
WHERE fecha >= '2026-06-01' AND fecha < '2026-08-01'
  AND metodo_pago != 'fondos'
GROUP BY TO_CHAR(fecha, 'Mon YYYY'), DATE_TRUNC('month', fecha)
ORDER BY DATE_TRUNC('month', fecha);
```

**Output esperado:**
```
periodo  | ingresos | cogs   | cogs_pct | margen_sin_cogs_pct
---------|----------|--------|----------|-------------------
Jun 2026 | 528.02   | 421.68 | 79.9     | 20.1
Jul 2026 | 691.45   | 419.53 | 60.7     | 39.3
```

**Interpretación:**
- Julio mejoró eficiencia de compra (COGS bajó de 79.9% a 60.7%)
- Eso explica por qué julio tuvo 181% más ganancia: mejor margen unitario
- **Acción:** Identifica qué cambió en compras/menu en julio y replica

---

### Paso 5: Análisis Diario para Identificar Patrones
```sql
-- Usa para ver tendencias intra-mes
SELECT 
  fecha::date AS dia,
  TO_CHAR(fecha, 'Day') AS dia_semana,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END) AS ingresos,
  SUM(CASE WHEN tipo='salida' THEN monto ELSE 0 END) AS gastos,
  SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) AS neto,
  ROUND(
    SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END) / 
    NULLIF(SUM(CASE WHEN tipo='entrada' THEN monto ELSE 0 END), 0) * 100, 
    1
  ) AS margen_pct
FROM movimientos_caja
WHERE fecha >= '2026-07-01' AND fecha < '2026-08-01'
  AND metodo_pago != 'fondos'
GROUP BY fecha::date, TO_CHAR(fecha, 'Day')
ORDER BY fecha::date;
```

**Output esperado:**
```
dia        | dia_semana | ingresos | gastos | neto  | margen_pct
-----------|------------|----------|--------|-------|----------
2026-07-01 | Tuesday    | 18.50    | 14.20  | 4.30  | 23.2
2026-07-02 | Wednesday  | 22.10    | 17.80  | 4.30  | 19.5
...
```

**Interpretación:**
- Identifica días de semana más rentables
- Útil para staffing, inventario, decisiones operativas

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

## 🎬 CASO REAL: ANTOJO24 JUNIO-JULIO 2026

### Los Números
| Métrica | Junio | Julio | Cambio |
|---------|-------|-------|--------|
| Ingresos | $528.02 | $691.45 | +30.9% |
| Gastos | $452.53 | $479.53 | +6.0% |
| Utilidad | $75.49 | $211.92 | +180.8% |
| Margen | 14.3% | 30.7% | +16.4 pp |
| COGS % | 79.9% | 60.7% | -19.2 pp |

### Qué Pasó (Análisis)

**Junio:** Operación estándar
- Margen bajo (14.3%) sugiere estructura de costos no optimizada
- COGS muy alto (79.9%) indica compras caras o desperdicio

**Julio: Cambio Significativo**
- Ingresos crecieron 30.9% → Demanda aumentó O cambio en mix de productos
- COGS bajó 19.2 pp → **Mejora en compras/eficiencia**
- Resultado: Utilidad se triplicó

### Hipótesis de Qué Cambió
1. **Cambio en proveedores:** Encontraste proveedor más barato
2. **Cambio en menu:** Enfocarse en items de margen más alto
3. **Reducción de desperdicio:** Mejor gestión de inventario
4. **Mezcla de canales:** Más ventas Yappy (29.9% margen) vs efectivo (8.6%)

### Recomendación
✅ **Urgente:** Identifica qué del combo anterior funcionó y bloquéalo en operación.
→ Si July es nueva "normalidad", espera 28-30% margen consistente de ahora en adelante.
→ Si July fue pico, ajusta expectativas y busca qué replicar.

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

- **Excluye siempre `metodo_pago='fondos'`** en análisis de rentabilidad: son compras desde la tesorería, no flujo operativo.
- **Saldo inicial cada mes:** Tanto Yappy como efectivo arrancan con $50.00 fijo (no incluir en utilidad neta).
- **Conciliación:** Usa `CIERRE_MES.md` para conciliación bancaria formal. Este doc es para business insights.
- **Frecuencia:** Mínimo mensual. Si tienes volumen, semanal es mejor.

---

## 📞 ¿PREGUNTAS?

Cada query está documentada. Adaptá los rangos de fechas (`fecha >= '2026-MM-01'`) para el período que necesites.

Si notas algo raro en los números, el problema usualmente está en:
1. **Fechas incorrectas** en movimientos (revisa `CIERRE_MES.md` paso 4)
2. **Categoría incorrecta** (inventario vs otro)
3. **Metodo_pago inconsistente** (incluir fondos sin querer)

Última revisión: Agosto 2026 — Antojo24 Backend Team
