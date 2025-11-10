#archivo cierre.py
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import os
import json
from db import fetch_all, fetch_one, fetch_all as query_fetch_all, execute, insert_many

cierre_bp = Blueprint("cierre", __name__)

def get_panama_datetime():
    return datetime.utcnow() - timedelta(hours=5)  # 👈 "utcnow" correcto

def parse_numeric_value(value, default, field_name):
    """Convierte valores enviados como string a float, con fallback y validación."""
    if value is None or value == "":
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Valor numérico inválido para {field_name}")

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
    if not sucursal_id:
        return jsonify({"error": "sucursal_id es requerido"}), 400

    inicio, fin, _ = get_rango_fecha_panama()

    try:
        # Debug completo de la consulta
        sql = "SELECT * FROM productos_pedido WHERE sucursal_id = :sucursal_id AND fecha >= :inicio AND fecha <= :fin"
        params = {"sucursal_id": sucursal_id, "inicio": inicio, "fin": fin}
        
        # Primero veamos si hay algún pedido sin filtros
        todos_pedidos = fetch_all("SELECT COUNT(*) as total, MIN(fecha) as primer_pedido, MAX(fecha) as ultimo_pedido FROM productos_pedido")
        
        # Ahora la consulta real
        rows = fetch_all(sql, params)
        
        # Si no hay resultados, veamos qué pedidos hay para esta sucursal
        if not rows:
            pedidos_sucursal = fetch_all(
                "SELECT COUNT(*) as total, MIN(fecha) as primer_pedido, MAX(fecha) as ultimo_pedido FROM productos_pedido WHERE sucursal_id = :sucursal_id",
                {"sucursal_id": sucursal_id}
            )
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
    print(f"[DEBUG CIERRE] >>> Inicia proceso para sucursal: {sucursal_id}, por: {creado_por}")

    if not sucursal_id or not creado_por:
        print(f"[DEBUG CIERRE] ERROR: Datos incompletos. Abortando.")
        return jsonify({"error": "Datos incompletos"}), 400

    now = get_panama_datetime()
    fecha_hoy = now.date()
    print(f"[DEBUG CIERRE] Fecha de hoy (objeto date): {fecha_hoy}, Tipo: {type(fecha_hoy)}")

    # 1. Validar si ya existe cierre
    sql_check = "SELECT * FROM cierres_caja WHERE sucursal_id = :sucursal_id AND fecha_cierre = :fecha_cierre LIMIT 1"
    # Usamos string para la fecha para asegurar consistencia con la inserción
    params_check = {"sucursal_id": sucursal_id, "fecha_cierre": fecha_hoy}
    print(f"[DEBUG CIERRE] Verificando existencia con params: {params_check}")
    cierre_existente = fetch_one(sql_check, params_check)
    print(f"[DEBUG CIERRE] Resultado de la verificación: {cierre_existente}")

    if cierre_existente:
        print(f"[DEBUG CIERRE] Cierre ya existe. Devolviendo 409.")
        return jsonify({"message": "Ya existe un cierre para hoy", "error": "Cierre duplicado"}), 409

    inicio, fin, _ = get_rango_fecha_panama()
    print(f"[DEBUG CIERRE] Rango de fechas para ventas: de {inicio} a {fin}")

    # 2. Obtener las ventas del día
    sql_ventas = "SELECT * FROM productos_pedido WHERE sucursal_id = :sucursal_id AND fecha >= :inicio AND fecha <= :fin"
    params_ventas = {"sucursal_id": sucursal_id, "inicio": inicio, "fin": fin}
    print(f"[DEBUG CIERRE] Consultando ventas con params: {params_ventas}")
    ventas = fetch_all(sql_ventas, params_ventas)

    if not ventas:
        print(f"[DEBUG CIERRE] No se encontraron ventas para el rango. Devolviendo 404.")
        return jsonify({"error": "No hay ventas registradas hoy"}), 404

    # 3. Agrupar por método de pago y calcular totales
    totales = {"total_general": 0, "ventas_realizadas": 0}
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

    # Convertir Decimal a float/int para serialización JSON
    productos_serializables = {k: float(v) for k, v in productos.items()}

    # Convertir totales de Decimal a float para consistencia
    for k, v in totales.items():
        totales[k] = float(v)

    print(f"[DEBUG CIERRE] Totales calculados: {totales}")
    print(f"[DEBUG CIERRE] Productos agrupados: {productos_serializables}")

    try:
        total_general = parse_numeric_value(data.get("total_general"), totales["total_general"], "total_general")
        total_efectivo = parse_numeric_value(data.get("total_efectivo"), totales.get("efectivo", 0), "total_efectivo")
        total_tarjeta = parse_numeric_value(data.get("total_tarjeta"), totales.get("tarjeta", 0), "total_tarjeta")
        total_transferencia = parse_numeric_value(
            data.get("total_transferencia"),
            totales.get("transferencia", 0) + totales.get("yappy", 0),
            "total_transferencia"
        )
        total_real = parse_numeric_value(data.get("total_real"), total_general, "total_real")
    except ValueError as parse_error:
        print(f"[DEBUG CIERRE] ERROR PARSE: {parse_error}")
        return jsonify({"error": str(parse_error)}), 400

    if total_real > total_general:
        sobrante = round(total_real - total_general, 2)
        faltante = 0.0
    elif total_real < total_general:
        faltante = round(total_general - total_real, 2)
        sobrante = 0.0
    else:
        sobrante = 0.0
        faltante = 0.0

    print(
        f"[DEBUG CIERRE] Totales finalizados => general: {total_general}, real: {total_real}, "
        f"sobrante: {sobrante}, faltante: {faltante}"
    )
    # 4. Insertar en cierres_caja
    insert_sql = (
        "INSERT INTO cierres_caja (sucursal_id, fecha_cierre, hora_cierre, total_efectivo, total_tarjeta, "
        "total_transferencia, total_general, total_real, sobrante, faltante, ventas_realizadas, creado_por, detalle_json) "
        "VALUES (:sucursal_id, :fecha_cierre, :hora_cierre, :total_efectivo, :total_tarjeta, :total_transferencia, "
        ":total_general, :total_real, :sobrante, :faltante, :ventas_realizadas, :creado_por, :detalle_json) RETURNING *"
    )
    params = {
        "sucursal_id": sucursal_id,
        "fecha_cierre": fecha_hoy,
        "hora_cierre": now.isoformat(),
        "total_efectivo": total_efectivo,
        "total_tarjeta": total_tarjeta,
        "total_transferencia": total_transferencia,
        "total_general": total_general,
        "total_real": total_real,
        "sobrante": sobrante,
        "faltante": faltante,
        "ventas_realizadas": totales["ventas_realizadas"],
        "creado_por": creado_por,
        "detalle_json": json.dumps(productos_serializables)
    }
    print(f"[DEBUG CIERRE] Params para la inserción final: {params}")

    try:
        resumen = fetch_one(insert_sql, params)
        print(f"[DEBUG CIERRE] Resultado de la inserción (resumen): {resumen}")
        if not resumen:
             print(f"[DEBUG CIERRE] La inserción no devolvió resumen. Devolviendo 500.")
             return jsonify({"error": "No se pudo registrar el cierre de caja"}), 500
        
        print(f"[DEBUG CIERRE] Proceso completado con éxito. Devolviendo 200.")
        resumen_payload = {
            "creado_por": resumen.get("creado_por", creado_por),
            "sucursal_id": resumen.get("sucursal_id", sucursal_id),
            "total_general": float(resumen.get("total_general", total_general)),
            "total_real": float(resumen.get("total_real", total_real)),
            "sobrante": float(resumen.get("sobrante", sobrante)),
            "faltante": float(resumen.get("faltante", faltante)),
            "ventas_realizadas": int(resumen.get("ventas_realizadas", totales["ventas_realizadas"]))
        }

        return jsonify({"message": "Cierre realizado con éxito", "resumen": resumen_payload}), 200

    except Exception as e:
        print(f"[DEBUG CIERRE] EXCEPCIÓN durante la inserción: {str(e)}")
        return jsonify({"error": f"Error al insertar cierre: {str(e)}"}), 500

@cierre_bp.route("/api/test-cierre", methods=["GET"])
def test_cierre():
    print("✅ Endpoint test-cierre activo")
    return jsonify({"message": "cierre_bp está cargado correctamente"}), 200


  
