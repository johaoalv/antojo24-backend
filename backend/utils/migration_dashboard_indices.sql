-- Índices para optimizar GET /api/dashboard: evita Seq Scan al filtrar/agrupar
-- pedidos y movimientos_caja por fecha (y opcionalmente por sucursal_id).
-- CONCURRENTLY evita bloquear la tabla durante la creación; por eso cada
-- sentencia debe ejecutarse fuera de un bloque de transacción explícito.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pedidos_sucursal_fecha
    ON pedidos (sucursal_id, fecha);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pedidos_fecha
    ON pedidos (fecha);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_movimientos_caja_sucursal_fecha
    ON movimientos_caja (sucursal_id, fecha);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_movimientos_caja_fecha
    ON movimientos_caja (fecha);
