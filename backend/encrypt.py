import bcrypt
from supabase import create_client

SUPABASE_URL = "TU_SUPABASE_URL"
SUPABASE_SERVICE_ROLE_KEY = "TU_SUPABASE_SERVICE_ROLE_KEY"
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Obtener empleados con PINs sin encriptar
response = supabase.table("empleados").select("id, pin").execute()

for empleado in response.data:
    hashed_pin = bcrypt.hashpw(empleado["pin"].encode(), bcrypt.gensalt()).decode()
    supabase.table("empleados").update({"pin": hashed_pin}).eq("id", empleado["id"]).execute()

print("PINs actualizados correctamente.")
