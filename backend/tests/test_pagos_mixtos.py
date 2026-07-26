"""
Test de Pagos Mixtos — antojo24
Verifica que un pedido con múltiples métodos de pago genera múltiples registros en movimientos_caja
"""

import requests
import uuid
import json
from datetime import datetime

# ─── Config ───
DEFAULT_URL = "http://localhost:5000"
BASE_URL = DEFAULT_URL
SUCURSAL = "test_pagos_mixtos"
PRODUCT_NAME = "test_hamburguesa"

# Track created resources
created_pedido_ids = []

# ─── Helpers ───

def api(method, path, json_data=None, params=None):
    """Helper para hacer llamadas a la API"""
    url = f"{BASE_URL}/api{path}"
    r = requests.request(method, url, json=json_data, params=params, timeout=15)
    return r

def post_pedido_mixto(total, metodos_pago_detalles):
    """
    Crea un pedido con pago mixto
    metodos_pago_detalles: [{"metodo_pago": "yappy", "monto": 60}, {"metodo_pago": "efectivo", "monto": 40}]
    """
    pid = str(uuid.uuid4())
    payload = {
        "pedido_id": pid,
        "pedido": [{"producto": PRODUCT_NAME, "cantidad": 1, "total_item": total}],
        "total_pedido": total,
        "metodos_pago_detalles": metodos_pago_detalles,
        "sucursal_id": SUCURSAL,
        "fecha": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "tipo_pedido": "local",
        "estado_pago": "pagado",
        "bolsas": 0
    }
    r = api("POST", "/pedido", json_data=payload)
    if r.status_code in (200, 201):
        created_pedido_ids.append(pid)
        print(f"✓ Pedido mixto creado: {pid}")
    else:
        print(f"✗ Error creando pedido mixto: {r.status_code}")
        print(f"  Response: {r.text}")
    return r, pid

def post_pedido_simple(total, metodo_pago):
    """Crea un pedido con un único método de pago (para comparación)"""
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
    r = api("POST", "/pedido", json_data=payload)
    if r.status_code in (200, 201):
        created_pedido_ids.append(pid)
        print(f"✓ Pedido simple creado: {pid}")
    else:
        print(f"✗ Error creando pedido simple: {r.status_code}")
    return r, pid

def get_movimientos_caja(referencia_id):
    """Obtiene los movimientos de caja para un pedido específico"""
    r = api("GET", "/finanzas/libro-caja", params={"sucursal_id": SUCURSAL})
    if r.status_code == 200:
        movimientos = r.json()
        # Filtrar por referencia_id (pedido_id)
        filtered = [m for m in movimientos if m.get("referencia_id") == referencia_id]
        return filtered
    return []

def cleanup():
    """Elimina pedidos de prueba"""
    print(f"\n{'='*60}")
    print("CLEANUP: Eliminando pedidos de prueba...")
    for pid in created_pedido_ids:
        try:
            r = api("DELETE", f"/pedido/{pid}")
            if r.status_code == 200:
                print(f"  ✓ Pedido {pid[:8]}... eliminado")
            else:
                print(f"  ✗ Error eliminando {pid[:8]}...: {r.status_code}")
        except Exception as e:
            print(f"  ✗ Exception: {e}")

# ─── TESTS ───

def test_1_pago_simple():
    """
    TEST 1: Pago Simple (Compatibilidad)
    - Crea un pedido con $100 en un método (yappy)
    - Verifica que crea 1 registro en movimientos_caja
    """
    print(f"\n{'='*60}")
    print("TEST 1: Pago Simple (Compatibilidad)")
    print("="*60)

    r, pedido_id = post_pedido_simple(total=100.0, metodo_pago="yappy")

    if r.status_code not in (200, 201):
        print(f"✗ FAIL: No se creó el pedido. Status: {r.status_code}")
        return False

    # Esperar un momento y consultar movimientos
    movimientos = get_movimientos_caja(pedido_id)

    print(f"\nMovimientos encontrados para pedido {pedido_id[:8]}...:")
    print(f"  Total de registros: {len(movimientos)}")

    if len(movimientos) == 0:
        print("✗ FAIL: No hay movimientos registrados")
        return False

    for m in movimientos:
        print(f"  - Método: {m.get('metodo_pago')}, Monto: ${m.get('monto')}, Ref: {m.get('referencia_id')[:8]}...")

    # Validar: debe haber exactamente 1 registro
    if len(movimientos) != 1:
        print(f"✗ FAIL: Se esperaba 1 movimiento, pero hay {len(movimientos)}")
        return False

    # Validar: el método debe ser 'yappy'
    if movimientos[0].get("metodo_pago") != "yappy":
        print(f"✗ FAIL: Método esperado 'yappy', obtuvo '{movimientos[0].get('metodo_pago')}'")
        return False

    # Validar: el monto debe ser $100
    if float(movimientos[0].get("monto", 0)) != 100.0:
        print(f"✗ FAIL: Monto esperado 100.0, obtuvo {movimientos[0].get('monto')}")
        return False

    print("✓ PASS: Pago simple funciona correctamente")
    return True

def test_2_pago_mixto_basico():
    """
    TEST 2: Pago Mixto Básico
    - Crea un pedido con $100: $60 Yappy + $40 efectivo
    - Verifica que crea 2 registros en movimientos_caja
    - Verifica montos y métodos
    """
    print(f"\n{'='*60}")
    print("TEST 2: Pago Mixto Básico ($60 Yappy + $40 Efectivo)")
    print("="*60)

    metodos = [
        {"metodo_pago": "yappy", "monto": 60.0},
        {"metodo_pago": "efectivo", "monto": 40.0}
    ]

    r, pedido_id = post_pedido_mixto(total=100.0, metodos_pago_detalles=metodos)

    if r.status_code not in (200, 201):
        print(f"✗ FAIL: No se creó el pedido. Status: {r.status_code}")
        return False

    movimientos = get_movimientos_caja(pedido_id)

    print(f"\nMovimientos para pedido {pedido_id[:8]}...:")
    print(f"  Total de registros: {len(movimientos)}")

    for m in movimientos:
        print(f"  - Método: {m.get('metodo_pago'):12} Monto: ${m.get('monto'):6.2f}")

    # Validar: debe haber exactamente 2 registros
    if len(movimientos) != 2:
        print(f"✗ FAIL: Se esperaba 2 movimientos, pero hay {len(movimientos)}")
        return False

    # Validar: suma de montos = $100
    suma = sum(float(m.get("monto", 0)) for m in movimientos)
    if abs(suma - 100.0) > 0.01:
        print(f"✗ FAIL: Suma de montos esperada 100.0, obtuvo {suma:.2f}")
        return False

    # Validar: debe haber un registro de yappy con $60
    yappy_movs = [m for m in movimientos if m.get("metodo_pago") == "yappy"]
    if len(yappy_movs) != 1 or float(yappy_movs[0].get("monto", 0)) != 60.0:
        print(f"✗ FAIL: No hay registro de Yappy con $60")
        return False

    # Validar: debe haber un registro de efectivo con $40
    efectivo_movs = [m for m in movimientos if m.get("metodo_pago") == "efectivo"]
    if len(efectivo_movs) != 1 or float(efectivo_movs[0].get("monto", 0)) != 40.0:
        print(f"✗ FAIL: No hay registro de efectivo con $40")
        return False

    print("✓ PASS: Pago mixto crea 2 registros correctamente")
    return True

def test_3_pago_mixto_tres_metodos():
    """
    TEST 3: Pago Mixto con 3 métodos
    - Crea un pedido con $100: $50 Yappy + $30 efectivo + $20 tarjeta
    - Verifica que crea 3 registros
    """
    print(f"\n{'='*60}")
    print("TEST 3: Pago Mixto con 3 Métodos ($50 Yappy + $30 Efectivo + $20 Tarjeta)")
    print("="*60)

    metodos = [
        {"metodo_pago": "yappy", "monto": 50.0},
        {"metodo_pago": "efectivo", "monto": 30.0},
        {"metodo_pago": "tarjeta", "monto": 20.0}
    ]

    r, pedido_id = post_pedido_mixto(total=100.0, metodos_pago_detalles=metodos)

    if r.status_code not in (200, 201):
        print(f"✗ FAIL: No se creó el pedido. Status: {r.status_code}")
        return False

    movimientos = get_movimientos_caja(pedido_id)

    print(f"\nMovimientos para pedido {pedido_id[:8]}...:")
    print(f"  Total de registros: {len(movimientos)}")

    for m in movimientos:
        print(f"  - Método: {m.get('metodo_pago'):12} Monto: ${m.get('monto'):6.2f}")

    # Validar: debe haber exactamente 3 registros
    if len(movimientos) != 3:
        print(f"✗ FAIL: Se esperaba 3 movimientos, pero hay {len(movimientos)}")
        return False

    # Validar: suma de montos = $100
    suma = sum(float(m.get("monto", 0)) for m in movimientos)
    if abs(suma - 100.0) > 0.01:
        print(f"✗ FAIL: Suma de montos esperada 100.0, obtuvo {suma:.2f}")
        return False

    print("✓ PASS: Pago mixto con 3 métodos funciona correctamente")
    return True

def test_4_validacion_suma():
    """
    TEST 4: Validación de suma de montos
    - Intenta crear un pedido con suma incorrecta ($60 + $30 = $90, pero total = $100)
    - Verifica que rechaza la solicitud
    """
    print(f"\n{'='*60}")
    print("TEST 4: Validación de Suma (Debe fallar: $60 + $30 ≠ $100)")
    print("="*60)

    metodos = [
        {"metodo_pago": "yappy", "monto": 60.0},
        {"metodo_pago": "efectivo", "monto": 30.0}
    ]

    r = api("POST", "/pedido", json_data={
        "pedido_id": str(uuid.uuid4()),
        "pedido": [{"producto": PRODUCT_NAME, "cantidad": 1, "total_item": 100.0}],
        "total_pedido": 100.0,
        "metodos_pago_detalles": metodos,
        "sucursal_id": SUCURSAL,
        "fecha": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "tipo_pedido": "local",
        "estado_pago": "pagado",
        "bolsas": 0
    })

    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:200]}")

    # Debe fallar (400)
    if r.status_code != 400:
        print(f"✗ FAIL: Se esperaba status 400, obtuvo {r.status_code}")
        return False

    print("✓ PASS: Validación de suma funciona correctamente")
    return True

# ─── Main ───

def main():
    print("\n" + "="*60)
    print("🧪 TESTS DE PAGOS MIXTOS")
    print("="*60)

    results = []

    # Ejecutar tests
    results.append(("Test 1: Pago Simple", test_1_pago_simple()))
    results.append(("Test 2: Pago Mixto (2 métodos)", test_2_pago_mixto_basico()))
    results.append(("Test 3: Pago Mixto (3 métodos)", test_3_pago_mixto_tres_metodos()))
    results.append(("Test 4: Validación de suma", test_4_validacion_suma()))

    # Resumen
    print(f"\n{'='*60}")
    print("RESUMEN DE TESTS")
    print("="*60)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    total_passed = sum(1 for _, p in results if p)
    total = len(results)

    print(f"\nTotal: {total_passed}/{total} tests pasaron")

    # Cleanup
    cleanup()

    # Exit code
    return 0 if total_passed == total else 1

if __name__ == "__main__":
    exit(main())
