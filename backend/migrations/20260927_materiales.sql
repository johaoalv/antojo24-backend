-- Ejecutar mediante scripts/migrate_materiales.py, con la aplicación detenida.
CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
ALTER TABLE insumos ADD COLUMN IF NOT EXISTS tipo text NOT NULL DEFAULT 'ingrediente' CHECK (tipo IN ('ingrediente', 'material'));
ALTER TABLE insumos ADD COLUMN IF NOT EXISTS codigo text;
CREATE UNIQUE INDEX IF NOT EXISTS insumos_codigo_unique ON insumos(codigo) WHERE codigo IS NOT NULL;
CREATE TABLE IF NOT EXISTS producto_materiales (
 producto_id integer NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
 insumo_id integer NOT NULL REFERENCES insumos(id) ON DELETE RESTRICT,
 cantidad numeric NOT NULL CHECK (cantidad > 0),
 PRIMARY KEY(producto_id, insumo_id)
);
CREATE TABLE IF NOT EXISTS materiales_por_pedido (
 codigo text PRIMARY KEY,
 insumo_id integer NOT NULL REFERENCES insumos(id) ON DELETE RESTRICT,
 cantidad numeric NOT NULL CHECK (cantidad >= 0 AND cantidad = trunc(cantidad))
);
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS consumos_registrados boolean NOT NULL DEFAULT false;
CREATE TABLE IF NOT EXISTS pedido_consumos (
 pedido_id uuid NOT NULL REFERENCES pedidos(pedido_id) ON DELETE CASCADE,
 insumo_id integer NOT NULL REFERENCES insumos(id) ON DELETE RESTRICT,
 cantidad numeric NOT NULL CHECK (cantidad > 0),
 costo_unitario numeric NOT NULL CHECK (costo_unitario >= 0),
 tipo text NOT NULL CHECK (tipo IN ('ingrediente', 'material')),
 PRIMARY KEY(pedido_id, insumo_id)
);
-- Copia de las asignaciones retiradas, sin alterar existencias ni costos.
CREATE TABLE IF NOT EXISTS recetas_materiales_migradas (
 receta_id integer PRIMARY KEY, producto text NOT NULL, insumo_id integer NOT NULL,
 cantidad_requerida numeric NOT NULL
);
