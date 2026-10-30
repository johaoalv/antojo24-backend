#archivo cierre.py
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import os
import json
from db import fetch_all, fetch_one, fetch_all as query_fetch_all, execute, insert_many, engine
from utils.resumen_cierre import calcular_resumen_cierre
from utils.tesoreria import dinero

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
        sql = """
            SELECT
                pp.*,
                p.tipo_pedido,
                p.estado_pago,
                p.total_pedido
            FROM productos_pedido pp
            JOIN pedidos p ON pp.pedido_id = p.pedido_id
            WHERE pp.sucursal_id = :sucursal_id
              AND pp.fecha >= :inicio
              AND pp.fecha <= :fin
        """
        params = {"sucursal_id": sucursal_id, "inicio": inicio, "fin": fin}
        rows = fetch_all(sql, params)

        if not rows:
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

    inicio = now.replace(hour=0, minute=0, second=0, microsecond=0)
    fin = inicio + timedelta(days=1)
    try:
        # Una misma instantánea para apertura, movimientos y saldo final.
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            calculo = calcular_resumen_cierre(conn, sucursal_id, inicio, fin)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "No se pudo calcular el saldo esperado del cierre"}), 500

    if not calculo["hay_movimientos"]:
        return jsonify({"error": "No hay movimientos registrados hoy"}), 404

    neto = {k: float(v) for k, v in calculo["neto"].items()}
    totales = {**neto, "total_general": float(calculo["entradas"] - calculo["salidas"]),
               "ventas_realizadas": calculo["ventas_realizadas"]}
    saldo_efectivo_esperado = float(calculo["finales"]["efectivo"])
    productos_serializables = {
        "entradas": float(calculo["entradas"]), "salidas": float(calculo["salidas"]), **neto,
        "saldos_iniciales": {k: float(v) for k, v in calculo["iniciales"].items()},
        "saldos_finales": {k: float(v) for k, v in calculo["finales"].items()},
        "traspasos": {k: float(v) for k, v in calculo["traspasos"].items()},
    }

    print(f"[DEBUG CIERRE] Totales calculados: {totales}")
    print(f"[DEBUG CIERRE] Desglose: {productos_serializables}")

    try:
        # Los totales provienen del servidor; el cliente solo aporta el conteo físico.
        total_general = totales["total_general"]
        total_efectivo = totales.get("efectivo", 0)
        total_tarjeta = totales.get("tarjeta", 0)
        total_transferencia = totales.get("transferencia", 0) + totales.get("yappy", 0)
        total_real = float(dinero(data.get("total_real")))
        if total_real < 0:
            raise ValueError("El efectivo contado no puede ser negativo")
    except ValueError as parse_error:
        print(f"[DEBUG CIERRE] ERROR PARSE: {parse_error}")
        return jsonify({"error": str(parse_error)}), 400

    # Sobrante/faltante: físico contado vs efectivo esperado
    if total_real > saldo_efectivo_esperado:
        sobrante = round(total_real - saldo_efectivo_esperado, 2)
        faltante = 0.0
    elif total_real < saldo_efectivo_esperado:
        faltante = round(saldo_efectivo_esperado - total_real, 2)
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
            "saldo_efectivo_esperado": saldo_efectivo_esperado,
            "saldos_finales": productos_serializables["saldos_finales"],
            "traspasos": productos_serializables["traspasos"],
            "sobrante": float(resumen.get("sobrante", sobrante)),
            "faltante": float(resumen.get("faltante", faltante)),
            "ventas_realizadas": int(resumen.get("ventas_realizadas", totales["ventas_realizadas"])),
            "desglose": {k: float(v) for k, v in totales.items() if k not in ["total_general", "ventas_realizadas"]}
        }

        return jsonify({"message": "Cierre realizado con éxito", "resumen": resumen_payload}), 200

    except Exception as e:
        print(f"[DEBUG CIERRE] EXCEPCIÓN durante la inserción: {str(e)}")
        return jsonify({"error": f"Error al insertar cierre: {str(e)}"}), 500

@cierre_bp.route("/api/pedidos-mes", methods=["GET"])
def get_pedidos_mes():
    sucursal_id = request.args.get("sucursal_id")
    if not sucursal_id:
        return jsonify({"error": "sucursal_id es requerido"}), 400

    try:
        now = get_panama_datetime()
        inicio_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
        fin_mes = now.strftime("%Y-%m-%dT23:59:59")

        sql = """
            SELECT
                p.pedido_id,
                p.fecha,
                p.total_pedido,
                p.metodo_pago,
                p.tipo_pedido,
                p.estado_pago
            FROM pedidos p
            WHERE p.sucursal_id = :sucursal_id
              AND p.fecha >= :inicio
              AND p.fecha <= :fin
            ORDER BY p.fecha DESC
        """
        rows = fetch_all(sql, {"sucursal_id": sucursal_id, "inicio": inicio_mes, "fin": fin_mes})

        # Calcular totales por método de pago
        por_metodo = {}
        total_mes = 0
        for row in rows:
            monto = float(row["total_pedido"] or 0)
            total_mes += monto
            metodo = row["metodo_pago"] or "otro"
            por_metodo[metodo] = por_metodo.get(metodo, 0) + monto

        return jsonify({
            "pedidos": rows,
            "resumen": {
                "total": total_mes,
                "cantidad": len(rows),
                "por_metodo": por_metodo
            }
        }), 200

    except Exception as e:
        print(f"[ERROR] get_pedidos_mes: {str(e)}")
        return jsonify({"error": "Error interno"}), 500

@cierre_bp.route("/api/test-cierre", methods=["GET"])
def test_cierre():
    print("✅ Endpoint test-cierre activo")
    return jsonify({"message": "cierre_bp está cargado correctamente"}), 200


  
