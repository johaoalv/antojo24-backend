-- Aplicar con scripts/migrate_traspasos.py antes de desplegar el backend.
CREATE TABLE IF NOT EXISTS tesoreria_aperturas (
    sucursal_id text PRIMARY KEY,
    fecha_inicio date NOT NULL,
    yappy numeric(18,2) NOT NULL,
    efectivo numeric(18,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS tesoreria_traspasos (
    id uuid PRIMARY KEY,
    sucursal_id text NOT NULL REFERENCES tesoreria_aperturas(sucursal_id),
    fecha timestamp NOT NULL,
    conservar_yappy numeric(18,2) NOT NULL,
    conservar_efectivo numeric(18,2) NOT NULL,
    yappy numeric(18,2) NOT NULL CHECK (yappy >= 0),
    efectivo numeric(18,2) NOT NULL CHECK (efectivo >= 0),
    CHECK (yappy + efectivo > 0)
);
CREATE INDEX IF NOT EXISTS tesoreria_traspasos_sucursal_fecha
    ON tesoreria_traspasos(sucursal_id, fecha DESC);
