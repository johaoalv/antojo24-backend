"""
Test de integracion financiera — antojo24
Simula ventas, gastos e inyecciones y verifica que el dashboard cuadra.
Usa sucursal_id='test_integration' para aislar datos de produccion.
"""

import requests
import uuid
import sys
import argparse
from datetime import datetime

# ─── Config ───
DEFAULT_URL = "http://localhost:5000"
BASE_URL = DEFAULT_URL
SUCURSAL = "test_integration"
PRODUCT_NAME = "test_integration_product"

# Track created resources for cleanup
created_pedido_ids = []
created_product_id = None

# ─── Helpers ───

def api(method, path, json=None, params=None):
    url = f"{BASE_URL}/api{path}"
    r = requests.request(method, url, json=json, params=params, timeout=15)
    return r

def get_dashboard():
    r = api("GET", "/dashboard", params={"sucursal_id": SUCURSAL})
    r.raise_for_status()
    return r.json()

def post_pedido(total, metodo_pago):
    pid = str(uuid.uuid4())
    payload = {
        "pedido_id": pid,
        "pedido": [{"producto": PRODUCT_NAME, "cantidad": 1, "total_item": total}],
        "total_pedido": total,
        "metodo_pago": metodo_pago,
        "sucursal_id": SUCURSAL,
        "fecha": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "tipo_pedido": "local",
        "estado_pago": "pagado",
        "bolsas": 0
    }
    r = api("POST", "/pedido", json=payload)
    if r.status_code in (200, 201):
        created_pedido_ids.append(pid)
    return r

def post_gasto(monto, metodo_pago, descripcion="Test gasto"):
    payload = {
        "monto": monto,
        "descripcion": descripcion,
        "categoria": "operativo",
        "metodo_pago": metodo_pago,
        "sucursal_id": SUCURSAL,
        "fecha": datetime.now().strftime("%Y-%m-%d")
    }
    return api("POST", "/gastos", json=payload)

def post_inyeccion(monto, metodo_pago, descripcion="Test inyeccion"):
    payload = {
        "monto": monto,
        "descripcion": descripcion,
        "sucursal_id": SUCURSAL,
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "metodo_pago": metodo_pago
    }
    return api("POST", "/inyecciones", json=payload)

def close(a, b, tol=0.02):
    return abs(float(a or 0) - float(b or 0)) < tol

# ─── Assertions ───

def check(label, dashboard, expected):
    """Check dashboard values against expected dict. Returns True if all pass."""
    mes = dashboard.get("mes_actual", {})
    flujo = mes.get("flujo_por_metodo", {})
    gastos_m = mes.get("gastos_por_metodo", {})

    ok = True
    details = []

    checks = {
        "saldo_mes": (mes.get("saldo_caja_mes", 0), expected.get("saldo_mes")),
        "ventas": (mes.get("ventas", 0), expected.get("ventas")),
        "flujo.efectivo": (flujo.get("efectivo", 0), expected.get("flujo_efect")),
        "flujo.yappy": (flujo.get("yappy", 0), expected.get("flujo_yappy")),
        "gastos.efectivo": (gastos_m.get("efectivo", 0), expected.get("gastos_efect")),
        "gastos.yappy": (gastos_m.get("yappy", 0), expected.get("gastos_yappy")),
    }

    for name, (actual, exp) in checks.items():
        if exp is None:
            continue
        if close(actual, exp):
            details.append(f"  OK  {name}: {actual}")
        else:
            details.append(f"  FAIL {name}: esperado={exp}, actual={actual}")
            ok = False

    status = "PASS" if ok else "FAIL"
    print(f"\n{'='*50}")
    print(f"[{status}] {label}")
    for d in details:
        print(d)

    return ok

# ─── Cleanup ───

def cleanup():
    print(f"\n{'='*50}")
    print("CLEANUP...")

    # Delete pedidos
    for pid in created_pedido_ids:
        try:
            r = api("DELETE", f"/pedido/{pid}")
            print(f"  Pedido {pid[:8]}... -> {r.status_code}")
        except Exception as e:
            print(f"  Pedido {pid[:8]}... -> ERROR: {e}")

    # Delete gastos by sucursal
    try:
        r = api("GET", "/gastos", params={"sucursal_id": SUCURSAL})
        if r.status_code == 200:
            for g in r.json():
                api("DELETE", f"/gastos/{g['id']}")
                print(f"  Gasto {g['id']} eliminado")
    except Exception as e:
        print(f"  Gastos cleanup error: {e}")

    # Delete inyecciones by sucursal
    try:
        r = api("GET", "/inyecciones", params={"sucursal_id": SUCURSAL})
        if r.status_code == 200:
            for i in r.json():
                api("DELETE", f"/inyecciones/{i['id']}")
                print(f"  Inyeccion {i['id']} eliminada")
    except Exception as e:
        print(f"  Inyecciones cleanup error: {e}")

    # Delete test product
    global created_product_id
    if created_product_id:
        try:
            r = api("DELETE", f"/productos/{created_product_id}")
            print(f"  Producto test -> {r.status_code}")
        except Exception as e:
            print(f"  Producto cleanup error: {e}")

    print("CLEANUP DONE")

# ─── Main ───

def main():
    global created_product_id, BASE_URL

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_URL)
    parser.add_argument("--cleanup-only", action="store_true")
    parser.add_argument("--no-cleanup", action="store_true")
    args = parser.parse_args()

    BASE_URL = args.base_url

    if args.cleanup_only:
        cleanup()
        return

    passed = 0
    total = 0

    try:
        # ─── SETUP: crear producto test ───
        print("SETUP: Creando producto de prueba...")
        r = api("POST", "/productos", json={"nombre": PRODUCT_NAME, "precio": 1.00})
        if r.status_code in (200, 201):
            data = r.json()
            created_product_id = data.get("id") or data.get("producto_id")
            print(f"  Producto creado: {created_product_id}")
        else:
            print(f"  WARN: Producto respuesta {r.status_code}: {r.text[:200]}")

        # ─── PASO 0: Baseline ───
        total += 1
        d = get_dashboard()
        if check("Paso 0 - Baseline", d, {
            "saldo_mes": 0, "ventas": 0
        }):
            passed += 1

        # ─── PASO 1: Venta efectivo $10 ───
        total += 1
        r = post_pedido(10.0, "efectivo")
        print(f"\n>> Venta efectivo $10 -> {r.status_code}")
        d = get_dashboard()
        if check("Paso 1 - Venta efectivo $10", d, {
            "saldo_mes": 10, "ventas": 10, "flujo_efect": 10
        }):
            passed += 1

        # ─── PASO 2: Venta yappy $5 ───
        total += 1
        r = post_pedido(5.0, "yappy")
        print(f"\n>> Venta yappy $5 -> {r.status_code}")
        d = get_dashboard()
        if check("Paso 2 - Venta yappy $5", d, {
            "saldo_mes": 15, "ventas": 15, "flujo_efect": 10, "flujo_yappy": 5
        }):
            passed += 1

        # ─── PASO 3: Gasto efectivo $3 ───
        total += 1
        r = post_gasto(3.0, "efectivo")
        print(f"\n>> Gasto efectivo $3 -> {r.status_code}")
        d = get_dashboard()
        if check("Paso 3 - Gasto efectivo $3", d, {
            "saldo_mes": 12, "ventas": 15, "flujo_efect": 7, "flujo_yappy": 5,
            "gastos_efect": 3
        }):
            passed += 1

        # ─── PASO 4: Gasto yappy $2 ───
        total += 1
        r = post_gasto(2.0, "yappy")
        print(f"\n>> Gasto yappy $2 -> {r.status_code}")
        d = get_dashboard()
        if check("Paso 4 - Gasto yappy $2", d, {
            "saldo_mes": 10, "ventas": 15, "flujo_efect": 7, "flujo_yappy": 3,
            "gastos_efect": 3, "gastos_yappy": 2
        }):
            passed += 1

        # ─── PASO 5: Inyeccion yappy $20 ───
        total += 1
        r = post_inyeccion(20.0, "yappy")
        print(f"\n>> Inyeccion yappy $20 -> {r.status_code}")
        d = get_dashboard()
        if check("Paso 5 - Inyeccion yappy $20", d, {
            "saldo_mes": 30, "ventas": 15, "flujo_efect": 7, "flujo_yappy": 23,
            "gastos_efect": 3, "gastos_yappy": 2
        }):
            passed += 1

        # ─── PASO 6: Inyeccion efectivo $15 ───
        total += 1
        r = post_inyeccion(15.0, "efectivo")
        print(f"\n>> Inyeccion efectivo $15 -> {r.status_code}")
        d = get_dashboard()
        if check("Paso 6 - Inyeccion efectivo $15", d, {
            "saldo_mes": 45, "ventas": 15, "flujo_efect": 22, "flujo_yappy": 23,
            "gastos_efect": 3, "gastos_yappy": 2
        }):
            passed += 1

        # ─── RESUMEN ───
        print(f"\n{'='*50}")
        print(f"RESULTADO FINAL: {passed}/{total} pasos pasaron")
        if passed == total:
            print(">>> SISTEMA FINANCIERO OK - Todo cuadra perfectamente")
        else:
            print(">>> HAY ERRORES - Revisar los FAIL arriba")

    finally:
        if not args.no_cleanup:
            cleanup()

    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
