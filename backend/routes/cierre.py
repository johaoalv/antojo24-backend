#archivo cierre.py
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from supabase import create_client
import os

cierre_bp = Blueprint("cierre", __name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

print("🚀 cierre.py se está cargando")


def get_panama_datetime():
    return datetime.utcnow() - timedelta(hours=5)  # 👈 "utcnow" correcto

def get_rango_fecha_panama():
    now = get_panama_datetime()
    fecha_str = now.strftime("%Y-%m-%d")
    inicio = f"{fecha_str}T00:00:00"
    fin = f"{fecha_str}T23:59:59"
    return inicio, fin, fecha_str

# --- Nuevo endpoint para pedidos del día ---
@cierre_bp.route("/api/pedidos-hoy", methods=["GET"])
def get_pedidos_hoy():
    sucursal_id = request.args.get("sucursal_id")
    print(f"[DEBUG] sucursal_id recibido: {sucursal_id}")  # 👈 Nuevo
    
    if not sucursal_id:
        return jsonify({"error": "sucursal_id es requerido"}), 400

    inicio, fin, _ = get_rango_fecha_panama()
    print(f"[DEBUG] Rango de fechas: {inicio} a {fin}")  # 👈 Nuevo

    try:
        response = supabase.table("productos_pedido") \
            .select("*") \
            .eq("sucursal_id", sucursal_id) \
            .gte("fecha", inicio) \
            .lte("fecha", fin) \
            .execute()
        
        print(f"[DEBUG] Respuesta de Supabase: {response}")  # 👈 Nuevo
        
        if not response.data:
            return jsonify({"error": "No hay pedidos hoy"}), 404

        return jsonify(response.data), 200
        
    except Exception as e:
        print(f"[ERROR] Excepción: {str(e)}")  # 👈 Nuevo
        return jsonify({"error": "Error interno"}), 500

@cierre_bp.route("/api/cierre-caja", methods=["POST"])
def cierre_caja():
    data = request.json
    sucursal_id = data.get("sucursal_id")
    creado_por = data.get("creado_por")

    if not sucursal_id or not creado_por:
        return jsonify({"error": "Datos incompletos"}), 400

    now = get_panama_datetime()
    fecha_hoy = now.date()

    # 1. Validar si ya existe cierre
    cierre_existente = supabase.table("cierres_caja") \
        .select("*") \
        .eq("sucursal_id", sucursal_id) \
        .eq("fecha_cierre", str(fecha_hoy)) \
        .execute()

    if cierre_existente.data:
        return jsonify({"error": "Ya existe un cierre para hoy"}), 409

    inicio, fin, fecha_hoy = get_rango_fecha_panama()

    # 2. Obtener las ventas del día
    ventas = supabase.table("productos_pedido") \
    .select("*") \
    .eq("sucursal_id", sucursal_id) \
    .gte("fecha", inicio) \
    .lte("fecha", fin) \
    .execute()

    if not ventas.data:
        return jsonify({"error": "No hay ventas registradas hoy"}), 404

    # 3. Agrupar por método de pago y calcular totales
    totales = {
        "efectivo": 0,
        "tarjeta": 0,
        "transferencia": 0,
        "total_general": 0,
        "ventas_realizadas": 0
    }
    productos = {}

    pedidos_unicos = set()

    for venta in ventas.data:
        metodo = venta.get("metodo_pago")
        total = venta.get("total_item", 0)
        producto = venta.get("producto")
        pedido_id = venta.get("pedido_id")

        totales[metodo] = totales.get(metodo, 0) + total
        totales["total_general"] += total

        if pedido_id not in pedidos_unicos:
            pedidos_unicos.add(pedido_id)
            totales["ventas_realizadas"] += 1

        if producto in productos:
            productos[producto] += venta.get("cantidad", 1)
        else:
            productos[producto] = venta.get("cantidad", 1)

    # 4. Insertar en cierres_caja
    resultado = supabase.table("cierres_caja").insert([{
        "sucursal_id": sucursal_id,
        "fecha_cierre": str(fecha_hoy),
        "hora_cierre": now.isoformat(),
        "total_efectivo": totales["efectivo"],
        "total_tarjeta": totales["tarjeta"],
        "total_transferencia": totales["transferencia"],
        "total_general": totales["total_general"],
        "ventas_realizadas": totales["ventas_realizadas"],
        "creado_por": creado_por,
        "detalle_json": productos
    }]).execute()

    return jsonify({"message": "Cierre realizado con éxito", "resumen": resultado.data[0]})

@cierre_bp.route("/api/test-cierre", methods=["GET"])
def test_cierre():
    print("✅ Endpoint test-cierre activo")
    return jsonify({"message": "cierre_bp está cargado correctamente"}), 200


  
