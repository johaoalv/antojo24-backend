# Ingredientes y materiales — despliegue coordinado

> **Credenciales de la BDD:** buscar el valor `DATABASE_PUBLIC_URL_MAIN` en el archivo `.env` de la raíz del proyecto. No publicar su valor ni contraseñas en este documento.


## Estado

Implementación local; no aplicada a staging ni producción. La prevalidación de staging
(.env del backend, 27 septiembre 2026) detectó que faltan papel antigrasa,
servilletas, caja de papas, envase de salsas y tapa de salsas. No se insertaron
artículos ni se copiaron IDs/costos de producción. También hay existencias negativas
y al menos un combo con una referencia a producto ausente en ese catálogo.
Completar y revisar esos datos antes de probar ventas.

## Modelo

- `insumos.tipo`: ingrediente/material. Conserva PK, stock, costo y referencias.
- `insumos.codigo`: clave única estable, independiente del ID de cada entorno.
- `producto_materiales`: referencias locales a producto e insumo, con cantidad.
- `materiales_por_pedido`: bolsa configurable (`codigo=bolsas`), una inicialmente.
- `pedido_consumos`: cantidades y costo unitario congelados al confirmar.
- `pedidos.consumos_registrados`: diferencia pedidos nuevos de históricos.
- `recetas_materiales_migradas`: copia de asignaciones retiradas para compatibilidad.

Los nombres de identificación inicial están exclusivamente en la migración. El
servicio de ventas resuelve los materiales desde las tablas, sin IDs numéricos
fijos. Si un nombre falta o es ambiguo, se aborta. Los productos que ya usaban
papel o servilleta reciben uno de cada uno; revisar el informe de asignaciones
para verificar que cubre todos los productos principales del catálogo de destino.
Para productos nuevos se configuran las asignaciones en Administración > Materiales.
Las papas heredan su caja y topping actuales; no se añade otro topping.
Las recetas directas de combos no gobiernan el consumo: lo hacen sus componentes.

## Prevalidación (solo lectura)

Definir `MIGRATION_DATABASE_URL` mediante el gestor de secretos o entorno de la
terminal, seleccionando explícitamente el destino. El script no carga `.env`.

```sh
python scripts/migrate_materiales.py
```

Revisar IDs locales, existencias, costos, asignaciones y recetas archivadas del
informe. Resolver duplicados o faltantes antes de avanzar. No se crean materiales
con stock/costo inventados. No se debe ejecutar el SQL directamente.

## Aplicación

1. Respaldar la base completa con la herramienta de backup de PostgreSQL/proveedor.
2. Detener escrituras del backend antiguo (ventana de mantenimiento).
3. Ejecutar `python scripts/migrate_materiales.py --apply` con el destino correcto.
   DDL, clasificación, traslado de recetas y registro de versión son una sola
   transacción. Un error revierte todo. El bloqueo tiene timeout de cinco segundos.
4. Desplegar backend y frontend de este cambio juntos. No reanudar el backend
   antiguo contra recetas ya migradas: omitiría materiales.
5. Revisar Administración > Materiales y Costeo, probar en staging una venta,
   una cancelación y la landing. Reanudar ventas solo cuando los datos sean correctos.
6. Repetir en producción después de validar staging. Reejecutar una migración
   completada no duplica asignaciones ni cambia cantidades editadas posteriormente.

La bolsa queda fuera del costo unitario del producto y se añade al costo total
real del pedido. El POS consulta su cantidad predeterminada; si falla la carga,
impide confirmar y ofrece reintentar. Permite cantidad cero explícita o varias.
La disponibilidad del costeo considera también los materiales por producto.
Las ventas rechazan stock insuficiente y no dejan pedidos/movimientos parciales.

## Cancelaciones e historial

Los pedidos nuevos devuelven su consumo registrado, incluidas bolsas, sin usar
recetas actuales. Una segunda cancelación no devuelve stock otra vez.

En pedidos antiguos se conserva la reconstrucción anterior con recetas actuales
y los materiales archivados al migrar. Es aproximada: no existía historial de
cantidades originales ni de bolsas manuales. No se inventan bolsas ni se
recalcula el costo histórico guardado. Si falta un componente necesario, la
cancelación devuelve un conflicto y requiere conciliación. Los IDs referenciados
por consumos nuevos no se pueden eliminar del inventario.

## Reversión

Si falla la transacción, PostgreSQL la revierte. Si se necesita revertir después
de aplicarla, mantener la aplicación detenida y restaurar el respaldo anterior
junto con el código anterior **solo si todavía no hubo ventas nuevas**. Si hubo
ventas, no restaurar un respaldo que las perdería: preparar una migración inversa
que preserve sus pedidos y consumos. No hay rollback destructivo automático.

## Pruebas locales

Usar una base PostgreSQL desechable en localhost. Las pruebas crean y eliminan
exclusivamente el esquema `test_materiales` y rechazan hosts remotos.

```sh
MATERIAL_TEST_DATABASE_URL=postgresql://localhost:55439/postgres python -m unittest discover -s tests -p test_materiales.py -v
```

Cubren IDs distintos, repetición, preview de solo lectura, faltantes, costos,
combos, topping adicional, bolsas ajustadas, cantidades inválidas, stock,
concurrencia, cancelación con recetas cambiadas, historial y API pública.
