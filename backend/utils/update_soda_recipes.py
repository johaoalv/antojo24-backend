from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_PUBLIC_URL")
engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    # 1. Eliminar receta antigua de 'soda'
    conn.execute(text("DELETE FROM recetas WHERE LOWER(producto) = 'soda'"))
    
    # 2. Asegurar que los insumos existan y obtener sus IDs
    res_coke = conn.execute(text("SELECT id FROM insumos WHERE LOWER(nombre) = 'soda coca-cola'")).fetchone()
    res_canada = conn.execute(text("SELECT id FROM insumos WHERE LOWER(nombre) = 'soda canada dry'")).fetchone()
    
    if res_coke:
        conn.execute(text("""
            INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
            VALUES ('coca cola', :insumo_id, 1)
            ON CONFLICT (producto, insumo_id) DO NOTHING
        """), {"insumo_id": res_coke[0]})
        print("Receta 'coca cola' añadida.")
        
    if res_canada:
        conn.execute(text("""
            INSERT INTO recetas (producto, insumo_id, cantidad_requerida)
            VALUES ('canada dry', :insumo_id, 1)
            ON CONFLICT (producto, insumo_id) DO NOTHING
        """), {"insumo_id": res_canada[0]})
        print("Receta 'canada dry' añadida.")

print("Migración de recetas completada.")
