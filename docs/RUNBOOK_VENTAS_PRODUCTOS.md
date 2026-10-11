# Runbook: ventas de productos, combos y planificación de compras

> **Credenciales de la BDD:** buscar el valor `DATABASE_PUBLIC_URL_MAIN` en el archivo `.env` de la raíz del proyecto. No publicar su valor ni contraseñas en este documento.


Última verificación del esquema: 11 de octubre de 2026.

## Objetivo

Obtener unidades vendidas de cualquier producto o combo, calcular el consumo
de sus componentes y estimar cuánto comprar para un período. Separar siempre
los datos históricos de las proyecciones y de los supuestos de rendimiento.

## 1. Definir el alcance y conectarse

Confirmar producto, sucursal y período. Si el producto se incorporó hace poco,
consultar todo el historial y mostrar la primera y última venta, además del
desglose mensual. La primera venta registrada no prueba la fecha de lanzamiento.

Buscar las credenciales en `DATABASE_PUBLIC_URL_MAIN` del archivo `.env`
de la raíz del proyecto. [CIERRE_MES.md](CIERRE_MES.md) explica cómo cargar
ese valor y conectarse. No copiar credenciales a reportes ni consultas guardadas.

Una vez cargada la variable desde `.env`:

```sh
psql "$DATABASE_PUBLIC_URL_MAIN" -X -v ON_ERROR_STOP=1
```

Ejecutar las consultas dentro de una transacción de solo lectura:

```sql
BEGIN READ ONLY;
-- Consultas de las siguientes secciones.
COMMIT;
```

Si la conexión falla por restricciones de red del entorno del agente, solicitar
el acceso de red correspondiente y repetir la consulta. No modificar ventas,
recetas ni inventario para hacer este análisis.

## 2. Verificar el esquema real

La documentación general puede describir columnas distintas a las existentes.
Consultar primero el esquema; adaptar los ejemplos si cambió:

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('pedidos', 'productos_pedido', 'productos',
                     'recetas', 'insumos', 'pedido_consumos')
ORDER BY table_name, ordinal_position;

SELECT MIN(fecha), MAX(fecha), COUNT(*) FROM pedidos;
SELECT estado_pago, tipo_pedido, sucursal_id, COUNT(*)
FROM pedidos
GROUP BY 1, 2, 3;
```

Fuentes verificadas en esta sesión:

| Tabla | Uso y columnas relevantes |
|---|---|
| `pedidos` | Cabecera: `pedido_id`, `fecha` (date), `estado_pago`, `sucursal_id`, `tipo_pedido`, `total_pedido` |
| `productos_pedido` | Líneas: `pedido_id`, `producto_id`, `producto`, `cantidad`, `total_item`, `costo_unitario`, `fecha` (timestamp) |
| `productos` | Catálogo: `id`, `nombre`, `es_combo`, `combo_items` (JSONB) |
| `recetas` | Ingredientes: `producto` (nombre), `insumo_id`, `cantidad_requerida` |
| `insumos` | Inventario: `id`, `nombre`, `unidad_medida`, `stock`, `porcion_estandar` |

`pedido_consumos` no existía en la base consultada, aunque el código local lo
referenciaba. Verificar su existencia antes de intentar usar consumos históricos.

## 3. Identificar el producto y los combos que lo contienen

Buscar por nombre para descubrir los IDs; luego usar los IDs en los cálculos.
Revisar también nombres históricos o líneas sin `producto_id`.

```sql
SELECT id, nombre, es_combo, combo_items, precio
FROM productos
WHERE nombre ILIKE '%producto a buscar%'
ORDER BY id;

SELECT producto_id, producto, SUM(cantidad) AS unidades
FROM productos_pedido
WHERE producto ILIKE '%producto a buscar%'
GROUP BY 1, 2
ORDER BY 2;
```

En `psql`, definir el ID elegido (25 es un ejemplo, reemplazarlo):

```sql
\set producto_id 25

SELECT c.id, c.nombre, (item->>'cantidad')::numeric AS unidades_por_combo
FROM productos c
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(c.combo_items, '[]'::jsonb)) item
WHERE c.es_combo
  AND (item->>'id')::integer = :producto_id
ORDER BY c.id;
```

Esta consulta identifica componentes directos. Si un combo contiene otro combo,
expandir también ese nivel y multiplicar cantidades. Los componentes y recetas
actuales no prueban que la composición histórica fuera la misma.

## 4. Contar ventas pagadas

La fuente de unidades es `productos_pedido`, unida a `pedidos` por `pedido_id`.
Usar `SUM(cantidad)`, no `COUNT(*)`: una línea puede contener varias unidades.
Filtrar `estado_pago = 'pagado'`; verificar estados nuevos si aparecen.
`movimientos_caja` no sirve para contar productos ni componentes de combos.

Ejemplo reutilizable en `psql`:

```sql
\set sucursal 'sucursal_santa_maria'
\set desde '2026-10-01'
\set hasta_exclusivo '2026-10-11'

SELECT pp.producto_id, pp.producto,
       SUM(pp.cantidad) AS unidades,
       COUNT(DISTINCT p.pedido_id) AS pedidos,
       MIN(p.fecha) AS primera_venta,
       MAX(p.fecha) AS ultima_venta,
       SUM(pp.total_item) AS ingresos_lineas
FROM productos_pedido pp
JOIN pedidos p USING (pedido_id)
WHERE p.estado_pago = 'pagado'
  AND p.sucursal_id = :'sucursal'
  AND p.fecha >= :'desde'::date
  AND p.fecha < :'hasta_exclusivo'::date
  AND pp.producto_id = :producto_id
GROUP BY 1, 2;
```

Para varios productos, sustituir el último filtro por
`pp.producto_id IN (25, 26, 28, 29, 30, 31, 32)` con los IDs reales.
Para todo el historial, quitar ambos filtros de fecha. Usar la fecha de la
cabecera como criterio consistente y señalar discrepancias con las líneas.
El límite superior es exclusivo: para incluir el día 30, usar el día 31.

Desglose mensual (con los mismos parámetros):

```sql
SELECT TO_CHAR(p.fecha, 'YYYY-MM') AS mes,
       pp.producto_id, pp.producto, SUM(pp.cantidad) AS unidades
FROM productos_pedido pp
JOIN pedidos p USING (pedido_id)
WHERE p.estado_pago = 'pagado'
  AND p.sucursal_id = :'sucursal'
  AND p.fecha >= :'desde'::date
  AND p.fecha < :'hasta_exclusivo'::date
  AND pp.producto_id = :producto_id
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;
```

Validar líneas huérfanas y pedidos excluidos antes de cerrar el resultado:

```sql
SELECT pp.producto_id, pp.producto, pp.cantidad,
       pp.sucursal_id, p.fecha, p.estado_pago
FROM productos_pedido pp
LEFT JOIN pedidos p USING (pedido_id)
WHERE pp.producto_id = :producto_id
  AND pp.sucursal_id = :'sucursal'
  AND (p.pedido_id IS NULL OR p.estado_pago IS DISTINCT FROM 'pagado');
```

Si hay huérfanos, IDs nulos o discrepancias de sucursal, reportarlos por separado
y revisar antes de sumarlos. No multiplicar `pedidos.total_pedido` al unirlo
con sus líneas; para ingresos del producto usar `total_item`.

## 5. Convertir ventas de combos a unidades del componente

Primero comprobar cómo se almacenan las líneas de un pedido de combo: si ya
incluyen sus componentes, sumarlos otra vez duplicaría el consumo.

```sql
SELECT pp.pedido_id, pp.producto_id, pp.producto, pp.cantidad
FROM productos_pedido pp
WHERE pp.pedido_id IN (
  SELECT pedido_id FROM productos_pedido WHERE producto_id = 26 LIMIT 5
)
ORDER BY pp.pedido_id, pp.producto_id;
```

Si se registra únicamente el combo como línea, calcular su componente directo
con esta consulta. Sumar unidades directas y unidades incluidas en combos:

```sql
WITH factores AS (
  SELECT :producto_id::integer AS vendido_id, 1::numeric AS factor
  UNION ALL
  SELECT c.id, SUM((item->>'cantidad')::numeric)
  FROM productos c
  CROSS JOIN LATERAL jsonb_array_elements(COALESCE(c.combo_items, '[]'::jsonb)) item
  WHERE c.es_combo AND (item->>'id')::integer = :producto_id
  GROUP BY c.id
)
SELECT pp.producto_id, pp.producto,
       SUM(pp.cantidad) AS unidades_vendidas,
       f.factor AS componente_por_unidad,
       SUM(pp.cantidad * f.factor) AS unidades_componente
FROM productos_pedido pp
JOIN pedidos p USING (pedido_id)
JOIN factores f ON f.vendido_id = pp.producto_id
WHERE p.estado_pago = 'pagado'
  AND p.sucursal_id = :'sucursal'
  AND p.fecha >= :'desde'::date
  AND p.fecha < :'hasta_exclusivo'::date
GROUP BY pp.producto_id, pp.producto, f.factor
ORDER BY pp.producto_id;
```

Para pasar del componente a sus ingredientes:

```sql
SELECT r.producto, r.insumo_id, i.nombre,
       r.cantidad_requerida, i.unidad_medida, i.porcion_estandar, i.stock
FROM recetas r
JOIN insumos i ON i.id = r.insumo_id
WHERE LOWER(TRIM(r.producto)) = (
  SELECT LOWER(TRIM(nombre)) FROM productos WHERE id = :producto_id
);
```

Consumo estimado = unidades del componente × cantidad de ingrediente por unidad.
No sumar a la vez la receta directa del combo y la receta de sus componentes
si describen el mismo consumo. Si hay un registro histórico de consumos,
preferirlo para medir descuentos reales, tras verificar su esquema y cobertura.
Sin él, comunicar que el consumo se estima con composición/receta actual.

## 6. Estimar compras y rentabilidad

Elegir una ventana reciente de días completos. Usar días calendario, incluidos
los días sin ventas, si la proyección también es por días calendario. Si se usan
días de operación, aplicar ese mismo criterio a los días futuros.

```text
Ritmo diario = unidades consumidas / días completos observados
Demanda futura = ritmo diario × días a cubrir
Necesidad = máximo(0, demanda futura + reserva + merma prevista - stock útil)
Paquetes a comprar = redondear hacia arriba(necesidad / rendimiento por paquete)

Gramos por paquete = libras × 453.59237
Rendimiento teórico = gramos por paquete / gramos por porción
```

Preguntar al negocio el peso por porción, tamaño y precio real del paquete,
rendimiento práctico y existencias disponibles. Si la unidad del insumo es
`unidad`, no asumir que representa gramos o una bolsa completa.
Separar reserva y merma de la demanda base. La compra puede distribuirse en
varias entregas según el espacio disponible.

```text
Ingresos proyectados = porciones vendidas × precio de venta
Resultado después del ingrediente = ingresos proyectados - costo del ingrediente
Ganancia completa = ingresos - ingredientes consumidos - aceite - empaque
                    - comisiones - otros costos atribuibles
```

No aplicar el precio individual a porciones incluidas en combos como si fueran
ventas adicionales. Para rentabilidad del combo, usar sus ingresos y todos sus
costos. Si sobran existencias, separar costo comprado de costo consumido.

## 7. Ejemplo de referencia: consulta del 11 de octubre de 2026

Historial disponible de pedidos: 6 de febrero a 10 de octubre de 2026.
Todas las ventas revisadas eran de `sucursal_santa_maria`.

| Producto | ID | Unidades pagadas |
|---|---:|---:|
| Combo 1 | 26 | 21 |
| Combo 2 | 28 | 5 |
| Combo 3 | 29 | 6 |
| Combo 4 | 30 | 6 |
| Combo 5 | 31 | 6 |
| Combo 6 | 32 | 5 |
| Papas fritas por separado | 25 | 27 |

Cada uno de esos combos incluía una porción: 49 en combos + 27 separadas =
76 porciones. No se encontraron líneas huérfanas ni canceladas para esos IDs.
Los otros combos del catálogo no contenían el producto 25.

| Período | En combos | Por separado | Total |
|---|---:|---:|---:|
| Septiembre | 26 | 20 | 46 |
| Octubre, días 1–10 | 23 | 7 | 30 |

Primera venta de papas: 19 de septiembre. Primera venta de los combos 1–6:
22 de septiembre. Estos datos son un corte histórico, no totales actualizados.

El negocio indicó bolsas de 5 lb y porciones de 150 g, con rendimiento práctico
de unas 15 porciones por bolsa. Precio aproximado: $7 y pico, sin confirmar.

- Ritmo de octubre: 30 / 10 = 3 porciones por día.
- Del 11 al 30 inclusive: 20 días × 3 = 60 porciones.
- Sin stock inicial ni reserva: 60 / 15 = 4 bolsas de 5 lb.
- Escenario de venta individual: 60 × $1.25 = $75.
- Con costo supuesto de $28: quedan $47 antes de aceite, empaque y otros gastos.

El escenario de $75 no representa el ingreso real del mix histórico, porque
parte de las porciones se vende dentro de combos. El costo real de las cuatro
bolsas sería algo superior a $28 si cuestan $7 y pico cada una.

## Entregable de cada consulta

Registrar fecha de corte, sucursal, período, IDs, unidades por producto,
componentes por combo, fuente del rendimiento, stock disponible y supuestos.
Mostrar el desglose mensual, la demanda base y la compra redondeada. Indicar
si la ventana es parcial y si se usó receta actual o consumo histórico.
