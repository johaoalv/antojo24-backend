import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Cargar variables de entorno
load_dotenv()

DATABASE_PUBLIC_URL = os.getenv("DATABASE_PUBLIC_URL")
if not DATABASE_PUBLIC_URL:
    raise RuntimeError("DATABASE_PUBLIC_URL no está configurada")

if DATABASE_PUBLIC_URL.startswith("postgres://"):
    DATABASE_PUBLIC_URL = DATABASE_PUBLIC_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_PUBLIC_URL)

def run_migration():
    with engine.begin() as conn:
        print("--- Creando tablas de inventario ---")
        
        # 1. Crear tabla de insumos
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS insumos (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL UNIQUE,
                stock DECIMAL(10, 2) DEFAULT 0,
                costo_unidad DECIMAL(10, 2) DEFAULT 0,
                unidad_medida VARCHAR(20) DEFAULT 'unidad',
                sucursal_id VARCHAR(50)
            );
        """))
        print("Tablar 'insumos' lista.")

        # 2. Crear tabla de recetas
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS recetas (
                id SERIAL PRIMARY KEY,
                producto VARCHAR(100) NOT NULL,
                insumo_id INTEGER REFERENCES insumos(id),
                cantidad_requerida DECIMAL(10, 2) NOT NULL,
                UNIQUE(producto, insumo_id)
            );
        """))
        print("Tabla 'recetas' lista.")

        # 3. Insertar insumos iniciales
        insumos_iniciales = [
            ("pan de hamburguesa", 100, 0.50, "unidad"),
            ("carne de hamburguesa", 100, 1.25, "unidad"),
            ("pan de hot dog", 100, 0.40, "unidad"),
            ("salchicha", 100, 0.35, "unidad"),
            ("soda coca-cola", 100, 0.60, "unidad"),
            ("soda canada dry", 100, 0.60, "unidad")
        ]
        
        for nombre, stock, costo, unidad in insumos_iniciales:
            conn.execute(text("""
                INSERT INTO insumos (nombre, stock, costo_unidad, unidad_medida)
                VALUES (:nombre, :stock, :costo, :unidad)
                ON CONFLICT (nombre) DO NOTHING
            """), {"nombre": nombre, "stock": stock, "costo": costo, "unidad": unidad})
        
        print("Insumos iniciales insertados.")

        # 4. Insertar recetas iniciales
        # Hamburguesa: 1 pan, 1 carne
        # Hot dog hawaiano / Chilli dog: 1 pan hot dog, 1 salchicha
        # Sodas
        
        recetas = [
            ("hamburguesa", "pan de hamburguesa", 1),
            ("hamburguesa", "carne de hamburguesa", 1),
            ("hot dog hawaiano", "pan de hot dog", 1),
            ("hot dog hawaiano", "salchicha", 1),
            ("chilli dog", "pan de hot dog", 1),
            ("chilli dog", "salchicha", 1),
            ("soda", "soda coca-cola", 1) # Por defecto Coca-Cola, se puede ajustar
        ]

        for prod, insumo_nombre, cant in recetas:
            insumo_id = conn.execute(text("SELECT id FROM insumos WHERE nombre = :nombre"), {"nombre": insumo_nombre}).scalar()
            if insumo_id:
                conn.execute(text("""
                    INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
                    VALUES (:producto, :insumo_id, :cantidad)
                    ON CONFLICT (producto, insumo_id) DO NOTHING
                """), {"producto": prod, "insumo_id": insumo_id, "cantidad": cant})
        
        print("Recetas iniciales insertadas.")
        print("--- Migración completada con éxito ---")

if __name__ == "__main__":
    run_migration()
