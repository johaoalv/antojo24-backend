# Plan: registrar compras desde una foto de factura

Estado: propuesta para implementación. No implementado.
Fecha: 26 de septiembre de 2026.

## Objetivo

Reducir el trabajo de registrar una compra dos veces: primero como gasto y después actualizando cada insumo. La aplicación leerá la factura, preparará una propuesta y permitirá corregirla. Solo después de la confirmación humana registrará el gasto, la salida de caja y el ingreso de inventario.

Ejemplo: una factura de El Machetazo contiene queso y carne. La aplicación muestra ambos artículos, sus cantidades y costos, propone los insumos correspondientes y explica cuánto stock se agregará. El usuario revisa y confirma una sola vez.

## Lo acordado

- Adjuntar una imagen de la factura.
- Mostrar claramente qué información detectó la aplicación.
- Permitir corregir, confirmar o descartar la propuesta antes de afectar gastos o inventario.
- Registrar conjuntamente la compra aprobada y sus efectos sobre los insumos.
- Mantener disponible el registro manual actual.

## Situación actual verificada

- `routes/gastos.py`: registrar un gasto crea un registro en `gastos` y una salida en `movimientos_caja` dentro de una transacción. No actualiza inventario.
- `routes/insumos.py`: editar un insumo reemplaza su stock y costo unitario. No representa una recepción de compra ni se vincula a una factura.
- Las recetas consumen insumos según su unidad y costo. Una conversión equivocada de paquetes a unidades afectaría existencias y costeo.
- El flujo nuevo debe sumar existencias sobre el stock vigente, no reutilizar la edición manual para sobrescribir un stock leído previamente.

## Experiencia propuesta

### 1. Adjuntar factura

Agregar la opción **Registrar compra desde factura** en la sección de Gastos del administrador.

El usuario adjunta una foto y selecciona la sucursal. La aplicación conserva el documento y crea un borrador. En el alcance inicial se propone una factura pagada, en una moneda, con un método de pago.

### 2. Detectar información

Un servicio de lectura de imágenes propone:

- Proveedor, fecha, número de factura y moneda, cuando sean legibles.
- Artículos tal como aparecen en el documento.
- Cantidad comprada, presentación, precio unitario y subtotal.
- Descuentos, impuestos y total, cuando aparezcan desglosados.
- Campos ilegibles o ambiguos que requieren revisión.

La extracción no registra gastos ni modifica inventario. No debe inventar cantidades o unidades ausentes. Los resultados se validan con un esquema y reglas aritméticas antes de mostrarlos.

### 3. Revisar la propuesta

Mostrar la imagen junto a una tabla editable:

| Dato de la factura | Decisión del usuario | Resultado previsto |
|---|---|---|
| Nombre del artículo | Seleccionar el insumo existente | Insumo que recibirá stock |
| Cantidad de paquetes | Confirmar unidades o contenido por paquete | Cantidad que se sumará |
| Precio y subtotal | Corregir importes y su interpretación | Costo por unidad del inventario |
| Impuestos y descuentos | Revisar su distribución | Costo final de la compra |
| Artículo ajeno al inventario | Clasificarlo como gasto sin stock | Registro monetario sin ingreso de insumos |

Ejemplo ilustrativo: **2 paquetes de queso de 24 rebanadas**, por un total de **$12**, equivalen a **48 unidades** y **$0.25 por unidad**, antes de otros ajustes. Esto solo aplica si el insumo queso se controla por rebanada.

Se debe ver el stock actual, la cantidad que se agregará y una proyección del stock resultante. La proyección es informativa: una venta concurrente puede cambiar el stock antes de confirmar.

Al pie: importe total que se registrará, método de pago, categoría, sucursal y avisos pendientes. Acciones: **Confirmar compra**, **Guardar borrador** y **Descartar**.

### 4. Confirmar una sola vez

El backend valida nuevamente y realiza en una misma transacción:

1. Bloquear y verificar el borrador; rechazar una segunda aplicación del mismo ingreso.
2. Validar la sucursal, los artículos, las unidades y la conciliación de importes.
3. Bloquear los insumos afectados en un orden estable y leer su stock y costo vigentes.
4. Registrar el gasto y su salida de caja mediante lógica compartida con el flujo actual.
5. Guardar el detalle aprobado de la compra y la conversión de cada artículo.
6. Sumar las cantidades recibidas al inventario y actualizar costos según la regla elegida.
7. Registrar los movimientos de inventario y marcar la compra como confirmada.

Si falla un paso, se revierte toda la transacción. No deben quedar gastos sin stock ni stock sin gasto. Las notificaciones se envían después del commit y sus fallos no provocan una segunda confirmación.

### 5. Consultar el resultado

Mostrar el comprobante de registro: factura, gasto asociado, artículos recibidos, cantidades agregadas y costos aplicados. Permitir consultar posteriormente la imagen y el detalle desde el gasto o historial de compras.

## Reglas importantes

### Conversión de unidades

- Separar la unidad de compra de la unidad del inventario: paquete, caja, kilogramo, gramo, botella, mililitro o unidad.
- Convertir kg a g y litros a ml cuando corresponda.
- Pedir el contenido por paquete cuando no sea conocido.
- No convertir peso a volumen sin un factor explícito.
- Recordar equivalencias aprobadas por proveedor y artículo, manteniéndolas editables en compras futuras.

### Costos

Decisión pendiente: usar **costo de la última compra** o **promedio ponderado**.

- Última compra: costo nuevo = costo imputado a la línea / unidades recibidas.
- Promedio ponderado: costo nuevo = (stock previo × costo previo + costo recibido) / (stock previo + unidades recibidas).

Si se elige promedio ponderado, definir primero el tratamiento del stock negativo, ya que el sistema permite ventas con existencias insuficientes. No aplicar esa fórmula sin una regla para ese caso.

También falta decidir cómo se asignan impuestos, descuentos y cargos generales al costo de los insumos. Usar aritmética decimal y una regla explícita de redondeo; la suma del detalle debe conciliar con el documento.

### Facturas duplicadas y reintentos

- Usar una clave de idempotencia y una restricción de unicidad para impedir doble confirmación por doble clic o reintento de red.
- Comparar la huella del archivo para reconocer una imagen repetida.
- Advertir sobre coincidencias de proveedor, número de factura, fecha y total. Una foto distinta del mismo documento no tendrá necesariamente la misma huella.
- Permitir revisar una coincidencia; no confundir una advertencia con una certeza de duplicidad.

### Artículos sin correspondencia

No crear insumos automáticamente por similitud de nombre. El usuario elige un insumo existente, decide crear uno mediante un flujo explícito o clasifica la línea como gasto sin stock.

No permitir confirmar líneas sin resolver. Si una factura mezcla inventario y gastos operativos, conservar la separación y asegurar que caja registre el total una sola vez. Si esa separación se posterga para una fase posterior, bloquear esas facturas en la primera versión con una explicación clara.

### Correcciones y anulaciones

Una compra confirmada debe corregirse con movimientos trazables. No devolver ni restar existencias usando recetas o conversiones actuales: usar el detalle aprobado que quedó guardado al confirmar.

Antes de habilitar el flujo, adaptar la eliminación de gastos vinculados a compras: no puede borrar únicamente el gasto y dejar el stock ingresado. En el MVP se puede bloquear esa eliminación y dirigir a un proceso explícito de anulación.

La anulación debe considerar consumos posteriores y la política de costos; no sobrescribir ciegamente el stock o costo con los valores anteriores a la compra.

## Diseño técnico propuesto

### Backend

Crear un módulo de compras que coordine extracción, borradores, validación y confirmación. Extraer la lógica compartida de gastos y caja para reutilizarla en la transacción, sin llamar a un endpoint HTTP desde otro.

Endpoints orientativos:

- `POST /api/compras/borradores`: subir imagen y crear borrador.
- `GET /api/compras/<id>`: obtener estado, extracción y propuesta.
- `PUT /api/compras/<id>`: guardar correcciones del borrador.
- `POST /api/compras/<id>/confirmar`: registrar la propuesta revisada con idempotencia.
- `POST /api/compras/<id>/descartar`: descartar un borrador sin efectos contables.

La extracción puede ser asíncrona; mostrar los estados pendiente, procesando, requiere revisión y error, con opción de reintentar o completar manualmente. Proveedor de lectura y límites de costo pendientes de elección.

### Datos

Validar el esquema real antes de preparar migraciones. Entidades propuestas:

- `compras`: proveedor, número de factura, fecha, sucursal, moneda, total, estado, archivo, huella, usuario, gasto vinculado y clave de confirmación.
- `compras_detalle`: texto original, insumo vinculado, cantidad comprada, conversión aprobada, cantidad recibida, costos, impuestos y descuentos aplicados.
- Movimientos de inventario asociados a la compra y su detalle, con cantidades, costos y momento de aplicación.
- Equivalencias proveedor/artículo → insumo y presentación, aprendidas de decisiones aprobadas.

Guardar por separado la extracción original y la versión corregida. Conservar la relación entre compra, gasto, caja y movimientos de stock.

### Frontend

- Entrada desde Gastos, con carga de foto y alternativa manual.
- Revisión de imagen y tabla editable antes de confirmar.
- Selector de insumos con conversión explícita y resumen de efectos.
- Confirmación deshabilitada mientras existan errores bloqueantes.
- Estado de envío que impida doble clic, recuperación del resultado tras un fallo de red e historial consultable.

### Archivos, acceso y servicio de lectura

- Guardar las facturas en almacenamiento privado persistente; no depender del disco temporal del servidor.
- Validar tamaño, formato real y dimensiones del archivo.
- Restringir lectura y confirmación por usuario autorizado y sucursal.
- Mantener credenciales del servicio de lectura en el backend.
- Tratar el texto de la factura como datos: nunca como instrucciones para ejecutar acciones.
- Documentar el servicio externo elegido, qué datos recibe y la política de conservación de imágenes.

## Fases de implementación

1. **Definir reglas y muestras:** revisar facturas reales, unidades de inventario, criterio de costo, impuestos, permisos y tratamiento de anulaciones.
2. **Ingreso manual unificado:** implementar borrador, detalle, confirmación transaccional e historial. Verificar que gasto, caja y stock se registran una sola vez.
3. **Lectura de imagen:** conectar el servicio de extracción a ese mismo borrador y construir la pantalla de revisión humana.
4. **Equivalencias y duplicados:** mejorar sugerencias de insumos, presentaciones y detección de facturas repetidas.
5. **Prueba piloto:** validar con copias de facturas en un entorno de prueba, revisar cálculos y habilitar el flujo de producción cuando esté aprobado.

## Criterios de aceptación

- Subir, editar o descartar un borrador no cambia gastos, caja ni inventario.
- Una factura aprobada con queso y carne registra el gasto y suma ambos insumos en una sola operación.
- Dos paquetes de 24 unidades agregan 48 unidades, no 2.
- Un doble clic o reintento no duplica la compra, el gasto ni el stock.
- Una venta simultánea no se pierde al ingresar inventario.
- Si falla una actualización, se revierten todos los efectos de la confirmación.
- Los totales aprobados concilian con la factura, incluidos impuestos y descuentos.
- Un artículo ilegible o sin correspondencia requiere resolución humana.
- Se puede consultar la factura original y el detalle que causó cada ingreso.
- La eliminación o anulación del gasto vinculado no deja inventario inconsistente.
- El registro manual actual sigue funcionando.

## Decisiones pendientes antes de implementar

1. Regla de actualización del costo y tratamiento del stock negativo.
2. Manejo de impuestos, descuentos, cargos y facturas mixtas.
3. Servicio de lectura de imágenes y presupuesto por factura.
4. Almacenamiento privado y conservación de documentos.
5. Alcance inicial: imágenes únicamente o también PDF y múltiples páginas.
6. Compras a crédito y pagos mixtos: incluidos inicialmente o para una fase posterior.
7. Política de anulación y corrección de compras ya confirmadas.

Este documento no autoriza cargas de facturas a terceros ni cambios en producción. Define el plan para desarrollar el flujo acordado.
