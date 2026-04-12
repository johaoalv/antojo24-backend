import psycopg2
from datetime import datetime, timedelta

# DB STAGING
DB_URL = "postgresql://postgres:vGOwapvdswGkTdEYvZpUogvkSqFVnEnx@maglev.proxy.rlwy.net:53994/railway"

def test_stress_contabilidad():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        print("\n--- INICIANDO TEST DE ESTRÉS CONTABLE ---")
        
        # 0. Limpieza de datos de prueba previos (para que el test sea puro)
        # Nota: Usamos una descripción única para poder borrar solo lo del test
        TEST_TAG = "TEST_CONT_2026"
        cur.execute(f"DELETE FROM movimientos_caja WHERE descripcion LIKE '%{TEST_TAG}%'")
        cur.execute(f"DELETE FROM pedidos WHERE pedido_id IN (SELECT referencia_id::uuid FROM movimientos_caja WHERE descripcion LIKE '%{TEST_TAG}%')")
        conn.commit()

        # --- ESCENARIO ---
        sucursal = "sucursal_santa_maria"
        saldos_esperados = {"efectivo": 0.0, "yappy": 0.0}
        
        # 1. Venta Local Efectivo ($10.50)
        p_id = "00000000-0000-0000-0000-000000000001"
        monto = 10.50
        print(f"1. Registrando Venta Local Efectivo: ${monto}")
        cur.execute("""
            INSERT INTO pedidos (pedido_id, total_pedido, metodo_pago, tipo_pedido, estado_pago, sucursal_id, fecha)
            VALUES (%s, %s, 'efectivo', 'local', 'pagado', %s, NOW())
        """, (p_id, monto, sucursal))
        cur.execute("""
            INSERT INTO movimientos_caja (fecha, tipo, categoria, monto, descripcion, sucursal_id, referencia_id, metodo_pago)
            VALUES (NOW(), 'entrada', 'venta', %s, %s, %s, %s, 'efectivo')
        """, (monto, f"Venta Local {TEST_TAG}", sucursal, p_id))
        saldos_esperados["efectivo"] += monto

        # 2. Venta Delivery Pendiente ($20.00) - NO debe crear movimiento de caja aún
        p_id_del = "00000000-0000-0000-0000-000000000002"
        monto_del = 20.00
        print(f"2. Registrando Venta Delivery (Pendiente): ${monto_del}")
        cur.execute("""
            INSERT INTO pedidos (pedido_id, total_pedido, metodo_pago, tipo_pedido, estado_pago, sucursal_id, fecha)
            VALUES (%s, %s, 'tarjeta', 'pedidosya', 'pendiente', %s, NOW())
        """, (p_id_del, monto_del, sucursal))
        # (Aquí NO insertamos en movimientos_caja, simulando el nuevo pedido.py)
        
        # 3. Inyección Capital Yappy ($50.00)
        monto_iny = 50.00
        print(f"3. Registrando Inyección Capital Yappy: ${monto_iny}")
        cur.execute("""
            INSERT INTO movimientos_caja (fecha, tipo, categoria, monto, descripcion, sucursal_id, metodo_pago)
            VALUES (NOW(), 'entrada', 'inversion', %s, %s, %s, 'yappy')
        """, (monto_iny, f"Aporte Capital {TEST_TAG}", sucursal))
        saldos_esperados["yappy"] += monto_iny

        # 4. Gasto Efectivo ($15.25)
        monto_gasto = 15.25
        print(f"4. Registrando Gasto Efectivo: ${monto_gasto}")
        cur.execute("""
            INSERT INTO movimientos_caja (fecha, tipo, categoria, monto, descripcion, sucursal_id, metodo_pago)
            VALUES (NOW(), 'salida', 'gastos', %s, %s, %s, 'efectivo')
        """, (monto_gasto, f"Compra Insumos {TEST_TAG}", sucursal))
        saldos_esperados["efectivo"] -= monto_gasto

        # 5. Liquidación de Delivery ($18.00 - Retienen comisión)
        print(f"5. Liquidando Pedido Delivery: Recibimos $18.00 de los $20.00 originales")
        # Actualizamos estado del pedido
        cur.execute("UPDATE pedidos SET estado_pago = 'pagado' WHERE pedido_id = %s", (p_id_del,))
        # Insertamos el movimiento real de dinero en Yappy
        cur.execute("""
            INSERT INTO movimientos_caja (fecha, tipo, categoria, monto, descripcion, sucursal_id, referencia_id, metodo_pago)
            VALUES (NOW(), 'entrada', 'venta', %s, %s, %s, %s, 'yappy')
        """, (18.00, f"Liquidación Real {TEST_TAG}", sucursal, p_id_del))
        saldos_esperados["yappy"] += 18.00

        conn.commit()

        # --- VALIDACIÓN FINAL ---
        print("\n--- VALIDACIÓN DE RESULTADOS ---")
        cur.execute("""
            SELECT metodo_pago, SUM(CASE WHEN tipo = 'entrada' THEN monto ELSE -monto END)
            FROM movimientos_caja
            WHERE descripcion LIKE %s
            GROUP BY metodo_pago
        """, (f'%{TEST_TAG}%',))
        
        resultados = cur.fetchall()
        print(f"{'METODO':<15} | {'ESPERADO':<10} | {'SISTEMA':<10} | {'STATUS'}")
        print("-" * 60)
        
        for met, saldo in resultados:
            exp = saldos_esperados.get(met, 0)
            status = "✅ OK" if abs(exp - float(saldo)) < 0.01 else "❌ ERROR"
            print(f"{met:<15} | ${exp:<9.2f} | ${float(saldo):<9.2f} | {status}")

        cur.close()
        conn.close()
        print("\nTest finalizado.")

    except Exception as e:
        print(f"\n❌ Error durante el test: {e}")

if __name__ == "__main__":
    test_stress_contabilidad()
