-- 1. Crear tabla de insumos
CREATE TABLE IF NOT EXISTS insumos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    stock DECIMAL(10, 2) DEFAULT 0,
    costo_unidad DECIMAL(10, 2) DEFAULT 0,
    unidad_medida VARCHAR(20) DEFAULT 'unidad',
    sucursal_id VARCHAR(50)
);

-- 2. Crear tabla de recetas
CREATE TABLE IF NOT EXISTS recetas (
    id SERIAL PRIMARY KEY,
    producto VARCHAR(100) NOT NULL,
    insumo_id INTEGER REFERENCES insumos(id),
    cantidad_requerida DECIMAL(10, 2) NOT NULL,
    UNIQUE(producto, insumo_id)
);

-- 3. Insertar insumos iniciales
INSERT INTO insumos (nombre, stock, costo_unidad, unidad_medida) VALUES
('pan de hamburguesa', 100, 0.50, 'unidad'),
('carne de hamburguesa', 100, 1.25, 'unidad'),
('pan de hot dog', 100, 0.40, 'unidad'),
('salchicha', 100, 0.35, 'unidad'),
('soda coca-cola', 100, 0.60, 'unidad'),
('soda canada dry', 100, 0.60, 'unidad')
ON CONFLICT (nombre) DO NOTHING;

-- 4. Insertar recetas iniciales
INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
SELECT 'hamburguesa', id, 1 FROM insumos WHERE nombre = 'pan de hamburguesa'
ON CONFLICT (producto, insumo_id) DO NOTHING;

INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
SELECT 'hamburguesa', id, 1 FROM insumos WHERE nombre = 'carne de hamburguesa'
ON CONFLICT (producto, insumo_id) DO NOTHING;

INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
SELECT 'hot dog hawaiano', id, 1 FROM insumos WHERE nombre = 'pan de hot dog'
ON CONFLICT (producto, insumo_id) DO NOTHING;

INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
SELECT 'hot dog hawaiano', id, 1 FROM insumos WHERE nombre = 'salchicha'
ON CONFLICT (producto, insumo_id) DO NOTHING;

INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
SELECT 'chilli dog', id, 1 FROM insumos WHERE nombre = 'pan de hot dog'
ON CONFLICT (producto, insumo_id) DO NOTHING;

INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
SELECT 'chilli dog', id, 1 FROM insumos WHERE nombre = 'salchicha'
ON CONFLICT (producto, insumo_id) DO NOTHING;

INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
SELECT 'soda', id, 1 FROM insumos WHERE nombre = 'soda coca-cola'
ON CONFLICT (producto, insumo_id) DO NOTHING;
