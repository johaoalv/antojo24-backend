# Backend Antojo24 - Guía para Agentes

Este documento proporciona una descripción completa del backend de Antojo24 para que los agentes IA puedan entender y trabajar eficientemente en el proyecto sin revisar archivo por archivo.

---

## 📋 Resumen Ejecutivo

**Antojo24** es un sistema de gestión para pequeños negocios de comida/bebidas. El backend es una API REST construida con **Flask** que gestiona pedidos, producción, finanzas y más.

- **Lenguaje:** Python 3.10+
- **Framework:** Flask + Flask-SocketIO
- **Base de datos:** PostgreSQL (Supabase)
- **Servidor:** Railway
- **Comunicación en tiempo real:** WebSockets (SocketIO)

---

## 🏗️ Estructura del Proyecto

```
backend/
├── app.py                    # Aplicación principal, configuración Flask
├── db.py                     # Conexión y funciones para base de datos
├── socket_instance.py        # Configuración SocketIO para WebSockets
├── requirements.txt          # Dependencias Python
│
├── routes/                   # Blueprints (módulos de funcionalidad)
│   ├── auth.py              # Autenticación (login por PIN)
│   ├── pedido.py            # Gestión de pedidos (crear, actualizar, confirmar)
│   ├── dashboard.py         # Datos analíticos y resumen diario
│   ├── produccion.py        # Gestión de producción y recetas
│   ├── productos.py         # CRUD de productos
│   ├── recetas.py           # Recetas de productos
│   ├── insumos.py           # Gestión de insumos/ingredientes
│   ├── mermas.py            # Registro de mermas (desperdicio)
│   ├── gastos.py            # Gastos operativos
│   ├── inyecciones.py       # Ingreso manual de stock
│   ├── cierre.py            # Cierre de caja/mes
│   ├── print.py             # Generación de PDFs para impresión
│   ├── costeo.py            # Cálculo de costos
│   └── finanzas.py          # Reportes financieros
│
├── utils/                    # Utilidades compartidas
│   ├── helpers.py           # Funciones auxiliares
│   ├── emit_dashboard_update.py   # Notificar cambios de dashboard (WebSocket)
│   ├── emit_stock_alerts.py       # Alertas de stock bajo (WebSocket)
│   └── update_soda_recipes.py    # Utilitario para actualizar recetas
│
├── scripts/                  # Scripts auxiliares
│   └── tools/audit_accounting.py  # Auditoría de contabilidad
│
└── tests/                    # Suite de pruebas
    ├── test_integracion_financiera.py
    ├── test_pagos_mixtos.py
    ├── test_stock_validation.py
    └── verify_api.py
```

---

## 🔌 Stack Tecnológico

### Dependencias Principales

| Librería | Versión | Propósito |
|----------|---------|----------|
| Flask | 3.0.2 | Framework web principal |
| Flask-SocketIO | 5.6.0 | WebSockets en tiempo real |
| SQLAlchemy | 2.0.45 | ORM y gestión de BD |
| psycopg2-binary | 2.9.11 | Driver PostgreSQL |
| python-dotenv | 1.0.1 | Variables de entorno |
| Flask-CORS | 4.0.1 | Control de CORS |
| gevent | 25.9.1 | ASGI para WebSockets |
| requests | 2.31.0 | Cliente HTTP (para APIs externas) |
| reportlab | 4.2.0 | Generación de PDFs |
| PyJWT | 2.7.0 | Tokens JWT (si aplica) |

### Dependencias de Servidor

- **Gunicorn**: Servidor WSGI en producción
- **Waitress**: Alternativa WSGI lightweight

---

## 🔐 Autenticación y Seguridad

### Sistema de Autenticación

- **Método:** PIN de acceso + validación de IP (opcional)
- **Endpoint:** `POST /api/login`
- **Datos requeridos:**
  - `pin`: PIN de 4 dígitos (verificado contra tabla `tiendas_acceso`)
  - `ip_cliente`: IP del cliente (validado si está configurado)

### Variables de Entorno Críticas

```ini
DATABASE_PUBLIC_URL=postgresql://user:pass@host:5432/dbname  # Conexión DB (OBLIGATORIA)
FRONTEND_URL=http://localhost:5173                           # URL frontend (CORS)
NETLIFY_URL=https://...                                      # URL Netlify (CORS alternativa)
N8N_API_KEY=...                                              # API key para n8n workflows
N8N_WEBHOOK_URL=https://...                                  # Webhooks n8n
PORT=5000                                                     # Puerto servidor (default: 5000)
```

---

## 📡 Arquitectura de Endpoints

Todos los endpoints usan prefijo `/api/`. Los Blueprints se registran automáticamente en `app.py`.

### 1. **Autenticación** (`/routes/auth.py`)
```
POST   /api/login                     # Login con PIN
```

### 2. **Pedidos** (`/routes/pedido.py`)
```
POST   /api/pedido                    # Crear nuevo pedido
PUT    /api/pedido/<pedido_id>        # Actualizar pedido
GET    /api/pedido/<pedido_id>        # Obtener detalles
DELETE /api/pedido/<pedido_id>        # Cancelar pedido
```
**Características especiales:**
- Soporta pagos simples y **pagos mixtos** (multiple métodos en un pedido)
- Emite actualizaciones en tiempo real al dashboard
- Valida stock disponible

### 3. **Dashboard** (`/routes/dashboard.py`)
```
GET    /api/dashboard                 # Datos resumidos del día
GET    /api/dashboard?sucursal_id=X   # Filtrar por sucursal
```
**Calcula:**
- Total ventas, margen neto
- Productos más vendidos
- Stock bajo
- Alerts

### 4. **Productos** (`/routes/productos.py`)
```
GET    /api/productos                 # Listar todos
POST   /api/productos                 # Crear
PUT    /api/productos/<id>            # Actualizar
DELETE /api/productos/<id>            # Eliminar
```

### 5. **Recetas** (`/routes/recetas.py`)
```
GET    /api/recetas                   # Listar recetas
POST   /api/recetas                   # Crear receta
PUT    /api/recetas/<id>              # Actualizar
```
**Nota:** Receta = composición de insumos para un producto

### 6. **Insumos** (`/routes/insumos.py`)
```
GET    /api/insumos                   # Listar insumos
POST   /api/insumos                   # Crear insumo
PUT    /api/insumos/<id>              # Actualizar
GET    /api/insumos/stock             # Stock disponible
```

### 7. **Producción** (`/routes/produccion.py`)
```
GET    /api/produccion                # Órdenes de producción
POST   /api/produccion                # Crear orden
PUT    /api/produccion/<id>/status    # Cambiar estado (pendiente→en progreso→listo)
```

### 8. **Mermas** (`/routes/mermas.py`)
```
POST   /api/mermas                    # Registrar desperdicio/pérdida
GET    /api/mermas                    # Historial de mermas
```

### 9. **Gastos** (`/routes/gastos.py`)
```
POST   /api/gastos                    # Registrar gasto
GET    /api/gastos                    # Listar gastos
PUT    /api/gastos/<id>               # Actualizar
```

### 10. **Inyecciones** (`/routes/inyecciones.py`)
```
POST   /api/inyecciones               # Ingreso manual de stock
GET    /api/inyecciones               # Historial
```

### 11. **Cierre** (`/routes/cierre.py`)
```
GET    /api/cierre                    # Datos de cierre de caja
POST   /api/cierre                    # Registrar cierre
GET    /api/cierre/mes                # Cierre de mes
```

### 12. **Finanzas** (`/routes/finanzas.py`)
```
GET    /api/finanzas/resumen          # Resumen financiero
GET    /api/finanzas/reportes         # Reportes detallados
```

### 13. **Costeo** (`/routes/costeo.py`)
```
GET    /api/costeo/<producto_id>      # Costo de un producto
POST   /api/costeo/recalcular         # Recalcular todos
```

### 14. **Impresión** (`/routes/print.py`)
```
POST   /api/print/pedido              # PDF del pedido
POST   /api/print/etiqueta            # Etiqueta de producto
GET    /api/print/comprobante/<id>    # Comprobante fiscal
```

### 15. **WebSocket Events** (`socket_instance.py`)
```
on "connect"                          # Cliente se conecta
emit "server_msg"                     # Mensaje del servidor
emit "dashboard_update"               # Actualización de dashboard
emit "stock_alert"                    # Alerta de stock bajo
emit "pedido_updated"                 # Pedido modificado
```

---

## 🗄️ Modelo de Datos (Tablas Principales)

Estas son las tablas esperadas en PostgreSQL (Supabase). No se usa un ORM modelado, se usan queries SQL directas.

### Tabla: `tiendas_acceso`
- `id`: PK
- `nombre_tienda`: Nombre del negocio
- `sucursal_id`: ID de sucursal (permite multi-local)
- `pin_acceso`: PIN para login (4 dígitos)
- `rol`: Rol del usuario (admin, vendedor, etc.)
- `ip_permitida`: IP autorizada (opcional, null = sin restricción)

### Tabla: `productos`
- `id`: PK
- `nombre`: Nombre del producto
- `precio`: Precio de venta
- `costo`: Costo unitario
- `stock_actual`: Stock disponible
- `stock_minimo`: Alerta si baja de este valor
- `unidad`: Unidad de medida (kg, unidad, litro, etc.)
- `sucursal_id`: Sucursal a la que pertenece
- `activo`: Boolean

### Tabla: `insumos`
- `id`: PK
- `nombre`: Nombre del insumo/ingrediente
- `stock_actual`: Stock disponible
- `stock_minimo`: Alerta si baja
- `precio_unitario`: Costo del insumo
- `unidad`: Unidad de medida
- `proveedor_id`: ID del proveedor (opcional)

### Tabla: `recetas`
- `id`: PK
- `producto_id`: ID del producto que crea
- `insumo_id`: ID del insumo usado
- `cantidad_necesaria`: Cantidad de insumo por unidad de producto
- `sucursal_id`: Sucursal

### Tabla: `pedidos`
- `id`: PK
- `pedido_id`: ID único del pedido (string)
- `fecha_creacion`: Timestamp
- `total_pedido`: Monto total
- `monto_recibido`: Dinero pagado
- `monto_vuelto`: Cambio
- `metodo_pago`: "EFECTIVO", "TARJETA", etc.
- `metodos_pago_detalles`: JSON con pagos mixtos `[{metodo, monto}, ...]`
- `estado`: "pendiente", "confirmado", "cancelado"
- `sucursal_id`: Sucursal que procesa

### Tabla: `ordenes_produccion`
- `id`: PK
- `pedido_id`: Referencia al pedido
- `producto_id`: Producto a producir
- `cantidad`: Cantidad a producir
- `estado`: "pendiente", "en_progreso", "listo", "cancelado"
- `fecha_creacion`: Cuándo se creó
- `fecha_completado`: Cuándo se terminó

### Tabla: `mermas`
- `id`: PK
- `producto_id` / `insumo_id`: Qué se perdió
- `cantidad`: Cantidad perdida
- `razon`: Motivo (vencimiento, rotura, etc.)
- `fecha`: Cuándo ocurrió
- `sucursal_id`: Dónde ocurrió

### Tabla: `gastos`
- `id`: PK
- `concepto`: Tipo de gasto
- `monto`: Cantidad
- `fecha`: Cuándo ocurrió
- `sucursal_id`: Sucursal asociada
- `descripcion`: Detalles adicionales

### Tabla: `cierre_caja`
- `id`: PK
- `fecha`: Fecha del cierre
- `monto_inicial`: Dinero inicial
- `total_ingresos`: Vendido en el día
- `total_egresos`: Gastos del día
- `monto_final`: Dinero en caja
- `diferencia`: Diferencia encontrada
- `sucursal_id`: Sucursal

### Tabla: `cierre_mes`
- `id`: PK
- `mes`: Mes/año (YYYY-MM)
- `ingresos_totales`: Total de ventas
- `gastos_totales`: Total de gastos
- `mermas_totales`: Pérdidas registradas
- `comisiones_bancarias`: Comisiones n8n/pagos
- `utilidad_neta`: Ganancia final
- `sucursal_id`: Sucursal

---

## 🛠️ Funciones y Helpers Clave

### Módulo: `db.py`

```python
# Obtener múltiples registros
fetch_all(sql: str, params: dict | None = None) -> list[dict]

# Obtener un registro
fetch_one(sql: str, params: dict | None = None) -> dict | None

# Ejecutar comando (INSERT, UPDATE, DELETE)
execute(sql: str, params: dict | None = None) -> dict

# Insertar múltiples registros
insert_many(table: str, rows: list[dict]) -> dict

# Obtener sesión SQLAlchemy
get_db() -> Generator[SessionLocal]
```

**Ejemplo de uso:**
```python
from db import fetch_one, execute

# Obtener usuario
user = fetch_one("SELECT * FROM tiendas_acceso WHERE pin_acceso = :pin", {"pin": "1234"})

# Actualizar
execute("UPDATE productos SET stock_actual = :stock WHERE id = :id", 
        {"stock": 50, "id": 1})
```

### Módulo: `utils/emit_dashboard_update.py`

```python
def emitir_dashboard_update(socketio, datos_dashboard, sucursal_id=None):
    """Emite actualización de dashboard a clientes conectados"""
```

Se llama automáticamente cuando hay cambios en pedidos/finanzas.

### Módulo: `utils/emit_stock_alerts.py`

```python
def emitir_stock_alerts(socketio, insumo_id, stock_actual, stock_minimo):
    """Emite alerta si stock cae por debajo del mínimo"""
```

---

## 📊 Patrones Comunes

### 1. **Estructura de Response**

```python
from flask import jsonify

# Éxito
return jsonify({"message": "OK", "data": {...}}), 200

# Error
return jsonify({"error": "Descripción del error"}), 400
```

### 2. **Validación de Datos**

```python
from flask import request

@route.route("/api/endpoint", methods=["POST"])
def handler():
    data = request.json
    if not data.get("campo_requerido"):
        return jsonify({"error": "campo_requerido es obligatorio"}), 400
```

### 3. **Transacciones en BD**

```python
from db import engine
from sqlalchemy import text

with engine.begin() as conn:
    conn.execute(text("UPDATE table SET col = :val"), {"val": value})
    conn.commit()  # Explícito
```

### 4. **Acceso a SocketIO desde Routes**

```python
from flask import current_app
from socket_instance import emit

@route.route("/api/action", methods=["POST"])
def action():
    # ... procesar lógica ...
    emit("server_msg", {"msg": "Acción completada"}, to=request.sid)
```

### 5. **Logging**

```python
from flask import current_app

current_app.logger.debug(f"Mensaje de debug: {variable}")
current_app.logger.info("Información importante")
current_app.logger.error("Error crítico")
```

---

## 🎯 Flujos Principales

### Flujo de Pedido (Pagos Simples y Mixtos)

1. **POST /api/pedido** recibe:
   - `pedido_id`: Identificador único
   - `items`: Lista de productos con cantidades
   - `total_pedido`: Monto total
   - `metodo_pago`: Método simple ó
   - `metodos_pago_detalles`: Array de `{metodo, monto}` para pagos mixtos

2. **Validación:**
   - Si `metodos_pago_detalles` existe y tiene >1 elemento → es pago mixto
   - Suma de montos debe ≈ total_pedido

3. **Procesamiento:**
   - Descontar stock de insumos por cada producto
   - Crear orden de producción
   - Registrar pedido en BD
   - Emitir actualización de dashboard
   - Emitir alertas de stock bajo

4. **Respuesta:**
   ```json
   {
     "message": "Pedido insertado correctamente",
     "pedido_id": "...",
     "monto_recibido": 100,
     "monto_vuelto": 10
   }
   ```

### Flujo de Dashboard

1. **GET /api/dashboard** obtiene:
   - Ventas del día (sum de pedidos confirmados)
   - Gastos del día
   - Margen neto
   - Top 5 productos más vendidos
   - Stock bajo (< stock_minimo)

2. **Filtros opcionales:**
   - `sucursal_id`: Solo datos de esa sucursal
   - Rango de fechas (si aplica)

3. **Notificación en tiempo real:**
   - Si se actualiza un pedido → emite evento WebSocket
   - Dashboard del cliente se actualiza automáticamente

---

## 🚀 Deployment

### Local (desarrollo)

```bash
cd backend
pip install -r requirements.txt
python app.py
# Servidor en http://127.0.0.1:5000
```

### Railway (producción)

- Configurado automáticamente con `railway.toml` / `render.yaml`
- Lee `DATABASE_PUBLIC_URL` de variables de entorno de Railway
- Puerto dinámico desde variable `PORT`

---

## 🔍 Debugging y Troubleshooting

### Problema: "DATABASE_PUBLIC_URL not set"
**Causa:** Falta variable de entorno
**Solución:** Agregar en `.env` o en Railway:
```
DATABASE_PUBLIC_URL=postgresql://...
```

### Problema: "CORS error: Origin not allowed"
**Causa:** Frontend URL no está en `CORS_ORIGINS`
**Solución:** Verificar variables `FRONTEND_URL` y `NETLIFY_URL`

### Problema: "WebSocket connection failed"
**Causa:** Cliente no puede conectar a servidor SocketIO
**Solución:**
- Verificar puerto está accesible
- Verificar `socketio.init_app()` en app.py
- Revisar logs con `app.logger.debug()`

### Debugging de Queries SQL

```python
from sqlalchemy import text
from db import engine

# Ver query generada
with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM products WHERE stock > :stock"), {"stock": 10})
    print(result.mappings().all())
```

---

## 📝 Tareas Comunes para Agentes

### ✅ Agregar un nuevo endpoint

1. Crear archivo en `routes/nuevo_feature.py`
2. Importar Blueprint: `nuevo_bp = Blueprint("nuevo", __name__)`
3. Decorar función: `@nuevo_bp.route("/api/nuevo", methods=["POST"])`
4. Registrar en `app.py`: `app.register_blueprint(nuevo_bp)`

### ✅ Modificar query de BD

1. Localizar query en el archivo del route
2. Usar `fetch_one()`, `fetch_all()`, o `execute()` de `db.py`
3. Pasar parámetros como dict con claves con prefijo `:` (ej: `:producto_id`)

### ✅ Agregar alerta en tiempo real

1. Usar `emit()` de `socket_instance.py`
2. Llamar desde route con `current_app.socketio`
3. Especificar evento y datos: `emit("event_name", {"data": value})`

### ✅ Agregar tabla nueva

1. Crear tabla en Supabase PostgreSQL
2. Agregar funciones en `db.py` si es necesario
3. Usar `fetch_all()` / `fetch_one()` / `execute()` en los routes

---

## 🔗 Referencias

- **Frontend:** `/frontend` (React/Vite)
- **Documentación de cierre:** `/CIERRE_MES.md`
- **Tests:** `/backend/tests/`
- **API Docs:** Ver comentarios en cada route

---

## 📞 Contacto y Preguntas

Para consultas no cubiertidas en este documento:
1. Revisar archivos de la ruta específica
2. Buscar en tests/ ejemplos de uso
3. Consultar historial de commits relacionados

---

**Última actualización:** 2026-07-26
**Versión:** 1.0
