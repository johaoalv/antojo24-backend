from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
import os

DATABASE_PUBLIC_URL = os.getenv("DATABASE_PUBLIC_URL")
if not DATABASE_PUBLIC_URL:
    # Dejar esto como error temprano: la app necesita DATABASE_PUBLIC_URL en Railway
    raise RuntimeError("DATABASE_PUBLIC_URL environment variable not set")

# SQLAlchemy / psycopg2 prefer the 'postgresql://' scheme
if DATABASE_PUBLIC_URL.startswith("postgres://"):
    DATABASE_PUBLIC_URL = DATABASE_PUBLIC_URL.replace("postgres://", "postgresql://", 1)

# Añadir sslmode=require para conexiones remotas si no es localhost
connect_args = {}
if "localhost" not in DATABASE_PUBLIC_URL and "127.0.0.1" not in DATABASE_PUBLIC_URL:
    connect_args = {"sslmode": "require"}

engine = create_engine(DATABASE_PUBLIC_URL, pool_pre_ping=True, connect_args=connect_args or {})
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def fetch_all(sql: str, params: dict | None = None):
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(r) for r in result.mappings().all()]

def fetch_one(sql: str, params: dict | None = None):
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        row = result.mappings().first()
        return dict(row) if row else None

def insert_many(table: str, rows: list[dict]):
    if not rows:
        return {"inserted": 0}
    keys = list(rows[0].keys())
    cols = ", ".join(keys)
    vals = ", ".join([f":{k}" for k in keys])
    sql = f"INSERT INTO {table} ({cols}) VALUES ({vals})"
    with engine.begin() as conn:
        conn.execute(text(sql), rows)
    return {"inserted": len(rows)}

def execute(sql: str, params: dict | None = None):
    """Execute a SQL statement with parameters and return affected rows"""
    with engine.connect() as conn:
        with conn.begin():  # Explicit transaction
            try:
                result = conn.execute(text(sql), params or {})
                conn.commit()  # Explicitly commit the transaction
                return {"rowcount": result.rowcount}
            except Exception as e:
                conn.rollback()  # Explicitly rollback on error
                raise e
