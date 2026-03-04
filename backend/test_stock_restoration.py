from dotenv import load_dotenv
load_dotenv()

from db import fetch_all, engine
from sqlalchemy import text
import uuid
from datetime import datetime

def test_delete_order_stock_restoration():
    print("=== INICIANDO TEST DE RESTAURACIÓN DE STOCK ===")
    
    # 1. Seleccionar un producto con receta
    receta_test = fetch_all("SELECT producto, insumo_id, cantidad_requerida FROM recetas LIMIT 1")[0]
    producto = receta_test['producto']
    insumo_id = receta_test['insumo_id']
    cant_requerida = float(receta_test['cantidad_requerida'])
    
    print(f"Producto a probar: {producto}")
    print(f"Insumo a monitorear (ID={insumo_id}): requiere {cant_requerida} unidades")

    # 2. Consultar stock inicial
    stock_inicial = float(fetch_all("SELECT stock FROM insumos WHERE id = :id", {"id": insumo_id})[0]['stock'])
    print(f"Stock inicial: {stock_inicial}")

    # 3. Crear un pedido simulado
    pedido_id = str(uuid.uuid4())
    print(f"Simulando venta del producto (ID Pedido: {pedido_id})...")
    
    with engine.begin() as conn:
        fecha_str = datetime.now().isoformat()
        # Insertar pedido
        conn.execute(text("""
            INSERT INTO pedidos (pedido_id, total_pedido, metodo_pago, sucursal_id, fecha, monto_recibido, monto_vuelto)
            VALUES (:pid, 10.0, 'efectivo', 'sucursal_test', :fecha, 10.0, 0.0)
        """), {"pid": pedido_id, "fecha": fecha_str})
        
        # Insertar producto del pedido
        conn.execute(text("""
            INSERT INTO productos_pedido (pedido_id, producto, cantidad, total_item, total_pedido, metodo_pago, sucursal_id, fecha)
            VALUES (:pid, :prod, 1, 10.0, 10.0, 'efectivo', 'sucursal_test', :fecha)
        """), {"pid": pedido_id, "prod": producto, "fecha": fecha_str})
        
        # Simular descuento de stock (como lo hace el endpoint POST /pedido)
        conn.execute(text("UPDATE insumos SET stock = stock - :cant WHERE id = :id"), 
                     {"cant": cant_requerida, "id": insumo_id})

    # 4. Verificar stock después de venta
    stock_post_venta = float(fetch_all("SELECT stock FROM insumos WHERE id = :id", {"id": insumo_id})[0]['stock'])
    print(f"Stock después de venta: {stock_post_venta} (Diferencia: {stock_post_venta - stock_inicial})")

    # 5. Llamar a la lógica de eliminación (simulando lo que hace el nuevo endpoint)
    print("Eliminando el pedido y restaurando stock...")
    
    # Aquí simulamos la lógica que pusimos en eliminar_pedido
    with engine.begin() as conn:
        # Recuperar items para restaurar
        items = conn.execute(text("SELECT producto, cantidad FROM productos_pedido WHERE pedido_id = :pid"), 
                              {"pid": pedido_id}).mappings().all()
        
        for item in items:
            prod_name = item['producto'].lower()
            cant_vende = float(item['cantidad'])
            
            # Receta
            ings = conn.execute(text("SELECT insumo_id, cantidad_requerida FROM recetas WHERE LOWER(producto) = :p"),
                                {"p": prod_name}).mappings().all()
            
            for ing in ings:
                devuelto = float(ing['cantidad_requerida']) * cant_vende
                conn.execute(text("UPDATE insumos SET stock = stock + :c WHERE id = :id"),
                             {"c": devuelto, "id": ing['insumo_id']})

        # Eliminar
        conn.execute(text("DELETE FROM productos_pedido WHERE pedido_id = :pid"), {"pid": pedido_id})
        conn.execute(text("DELETE FROM pedidos WHERE pedido_id = :pid"), {"pid": pedido_id})

    # 6. Verificar stock final
    stock_final = float(fetch_all("SELECT stock FROM insumos WHERE id = :id", {"id": insumo_id})[0]['stock'])
    print(f"Stock final: {stock_final}")

    if stock_final == stock_inicial:
        print("✅ TEST EXITOSO: El stock volvió a su nivel original.")
    else:
        print(f"❌ TEST FALLIDO: El stock es {stock_final}, se esperaba {stock_inicial}")

if __name__ == "__main__":
    test_delete_order_stock_restoration()
