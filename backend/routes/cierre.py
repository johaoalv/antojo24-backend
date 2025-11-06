#archivo cierre.py
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import os
from db import fetch_all, fetch_one, fetch_all as query_fetch_all, execute, insert_many

cierre_bp = Blueprint("cierre", __name__)

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
        # Debug completo de la consulta
        sql = "SELECT * FROM productos_pedido WHERE sucursal_id = :sucursal_id AND fecha >= :inicio AND fecha <= :fin"
        params = {"sucursal_id": sucursal_id, "inicio": inicio, "fin": fin}
        
        print("[DEBUG] -------- Diagnóstico de consulta --------")
        print(f"SQL: {sql}")
        print(f"Parámetros: {params}")
        
        # Primero veamos si hay algún pedido sin filtros
        todos_pedidos = fetch_all("SELECT COUNT(*) as total, MIN(fecha) as primer_pedido, MAX(fecha) as ultimo_pedido FROM productos_pedido")
        print(f"[DEBUG] Total pedidos en BD: {todos_pedidos}")
        
        # Ahora la consulta real
        rows = fetch_all(sql, params)
        print(f"[DEBUG] Respuesta de BD: {rows}")
        
        # Si no hay resultados, veamos qué pedidos hay para esta sucursal
        if not rows:
            pedidos_sucursal = fetch_all(
                "SELECT COUNT(*) as total, MIN(fecha) as primer_pedido, MAX(fecha) as ultimo_pedido FROM productos_pedido WHERE sucursal_id = :sucursal_id",
                {"sucursal_id": sucursal_id}
            )
            print(f"[DEBUG] Pedidos de esta sucursal: {pedidos_sucursal}")
            return jsonify({"error": "No hay pedidos hoy"}), 404

        return jsonify(rows), 200

    except Exception as e:
        print(f"[ERROR] Excepción: {str(e)}")
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
    sql_check = "SELECT * FROM cierres_caja WHERE sucursal_id = :sucursal_id AND fecha_cierre = :fecha_cierre LIMIT 1"
    cierre_existente = fetch_one(sql_check, {"sucursal_id": sucursal_id, "fecha_cierre": str(fecha_hoy)})

    if cierre_existente:
        return jsonify({"error": "Ya existe un cierre para hoy"}), 409

    inicio, fin, fecha_hoy = get_rango_fecha_panama()

    # 2. Obtener las ventas del día
    sql_ventas = "SELECT * FROM productos_pedido WHERE sucursal_id = :sucursal_id AND fecha >= :inicio AND fecha <= :fin"
    ventas = fetch_all(sql_ventas, {"sucursal_id": sucursal_id, "inicio": inicio, "fin": fin})

    if not ventas:
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

    for venta in ventas:
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
    insert_sql = "INSERT INTO cierres_caja (sucursal_id, fecha_cierre, hora_cierre, total_efectivo, total_tarjeta, total_transferencia, total_general, ventas_realizadas, creado_por, detalle_json) VALUES (:sucursal_id, :fecha_cierre, :hora_cierre, :total_efectivo, :total_tarjeta, :total_transferencia, :total_general, :ventas_realizadas, :creado_por, :detalle_json) RETURNING *"
    params = {
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
    }

    try:
        resumen = fetch_one(insert_sql, params)
    except Exception:
        # Fallback: intentar insert simple sin RETURNING
        insert_result = insert_many("cierres_caja", [params])
        resumen = params if insert_result.get("inserted", 0) > 0 else None

    return jsonify({"message": "Cierre realizado con éxito", "resumen": resumen})

@cierre_bp.route("/api/test-cierre", methods=["GET"])
def test_cierre():
    print("✅ Endpoint test-cierre activo")
    return jsonify({"message": "cierre_bp está cargado correctamente"}), 200


  
