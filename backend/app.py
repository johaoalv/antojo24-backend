from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from flask_cors import CORS
from supabase import create_client, Client
import bcrypt

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configurar CORS: Permite todos los orígenes en local, y en producción Netlify
CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_URL", "*")}})

# Variables de entorno para Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
# Crear el cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

@app.route("/api/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Datos JSON inválidos"}), 400

        required_fields = ["nombre", "apellido", "cedula", "pin", "tienda", "telefono", "correo"]
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return jsonify({"error": f"Faltan los siguientes campos: {', '.join(missing_fields)}"}), 400

        nombre = data["nombre"].strip()
        apellido = data["apellido"].strip()
        cedula = data["cedula"].strip()
        pin = data["pin"].strip()
        tienda = data["tienda"].strip()
        telefono = data["telefono"].strip()
        correo = data["correo"].strip()

        # Validaciones específicas
        if len(pin) != 6 or not pin.isdigit():
            return jsonify({"error": "El PIN debe ser un número de 6 dígitos."}), 400

        # 🔹 Encriptamos el PIN antes de guardarlo
        hashed_pin = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()
        print(f"Hashed PIN generado: {hashed_pin}") 

        # 🔹 Insertamos en Supabase
        response = supabase.table("empleados").insert({
            "nombre": nombre,
            "apellido": apellido,
            "cedula": cedula,
            "pin": hashed_pin,
            "tienda": tienda,
            "telefono": telefono,
            "correo": correo
        }).execute()

        if response.data:
            return jsonify({"message": "Empleado registrado correctamente"}), 201
        else:
            return jsonify({"error": "Error al registrar empleado"}), 500

    except Exception as e:
        return jsonify({"error": f"Error interno del servidor: {str(e)}"}), 500


#Funcion para verificar PIN
def verify_pin(pin, hashed_pin):
    return bcrypt.checkpw(pin.encode(), hashed_pin.encode())

#Endpoint para validar PIN en Supabase
@app.route("/api/login", methods=["POST"])
def login ():
    data = request.json
    cedula = data.get("cedula")
    pin = data.get("pin")

    if  not cedula or not pin:
        return jsonify({"error": "Cédula y PIN son requeridos."}), 400
    
    # Buscar al empleado en la base de datos por su cédula
    response = supabase.table("empleados").select("nombre, apellido, pin").eq("cedula", cedula).execute()
    
    # Si no se encuentra el empleado, se devuelve un error
    if not response.data:
        return jsonify({"error": "Empleado no encontrado."}), 404
    
    empleado = response.data[0]  # Se obtiene la información del empleado
    print(f"PIN ingresado: {pin}")
    print(f"PIN en la BD: {empleado['pin']}")

    
    # Verificar si el PIN ingresado es correcto
    if verify_pin(pin, empleado["pin"]):
        return jsonify({
                "message": "Inicio de sesión exitoso", 
                "nombre": empleado["nombre"], 
                "apellido": empleado["apellido"]
                }), 200
    else:
        return jsonify({"error": "PIN incorrecto."}), 401


# Endpoint para insertar en la tabla productos_pedido
@app.route("/api/pedido", methods=["POST"])
def pedido():
    data = request.json
    productos = [
    {
        "pedido_id": item["pedido_id"],
        "producto": item["producto"],
        "cantidad": item["cantidad"],
        "total_item": item["total_item"], 
        "total_pedido": data["total_pedido"],  
        "metodo_pago": data["metodo_pago"],    
    }
    for item in data["pedido"]  
]

    response = supabase.table("productos_pedido").insert(productos).execute()

    if response.data:
        return jsonify({"message": "Pedido insertado correctamente en Supabase"}), 201
    else:
        return jsonify({"error": "Error al insertar en Supabase", "details": response}), 500

# Manejo de preflight request para CORS en Netlify
@app.route("/api/pedido", methods=["OPTIONS"])
def handle_options():
    return '', 200

@app.route("/api/dashboard", methods=["GET"])
def get_dashboard():
    from datetime import date, timedelta

    fecha_hoy = str(date.today())  # Obtiene la fecha de hoy en formato YYYY-MM-DD
    fecha_ayer = str(date.today() - timedelta(days=1))  # Fecha de ayer

    # 🔹 Obtener TODOS los pedidos de Supabase
    response_pedidos = supabase.table("pedidos") \
        .select("total_pedido, fecha, metodo_pago") \
        .execute()

    response_productos = supabase.table("productos_pedido") \
        .select("producto, cantidad") \
        .execute()

    if not response_pedidos.data or not response_productos.data:
        return jsonify({"error": "Error al obtener datos del dashboard"}), 500

    pedidos = response_pedidos.data
    productos = response_productos.data

    # 🔹 1 & 2: Calcular ventas de hoy y ayer
    ventas_hoy = sum(p["total_pedido"] for p in pedidos if p["fecha"] == fecha_hoy)
    ventas_ayer = sum(p["total_pedido"] for p in pedidos if p["fecha"] == fecha_ayer)

    # 🔹 3: Producto más vendido
    productos_vendidos = {}
    for p in productos:
        if p["producto"] in productos_vendidos:
            productos_vendidos[p["producto"]] += p["cantidad"]
        else:
            productos_vendidos[p["producto"]] = p["cantidad"]

    producto_mas_vendido = max(productos_vendidos, key=productos_vendidos.get) if productos_vendidos else "N/A"

    # 🔹 4: Método de pago más usado
    metodos_pago = {}
    for p in pedidos:
        if p["metodo_pago"] in metodos_pago:
            metodos_pago[p["metodo_pago"]] += 1
        else:
            metodos_pago[p["metodo_pago"]] = 1

    metodo_pago_mas_usado = max(metodos_pago, key=metodos_pago.get) if metodos_pago else "N/A"

    # 🔹 5: % de variación en ventas
    variacion_porcentaje = (
        ((ventas_hoy - ventas_ayer) / ventas_ayer * 100) if ventas_ayer > 0 else 100
    )

    return jsonify({
        "ventas_hoy": ventas_hoy,
        "ventas_ayer": ventas_ayer,
        "producto_mas_vendido": producto_mas_vendido,
        "metodo_pago_mas_usado": metodo_pago_mas_usado,
        "variacion_porcentaje": round(variacion_porcentaje, 2)
    }), 200


# Configurar el puerto correctamente en local y Railway
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
