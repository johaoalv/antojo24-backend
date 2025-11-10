# utils/emit_dashboard_update.py

from datetime import date, timedelta
from socket_instance import socketio
from db import fetch_all # 👈 Importamos la función correcta

def emitir_dashboard_update():
    try:
        fecha_hoy = str(date.today())
        fecha_ayer = str(date.today() - timedelta(days=1))

        # Reutilizamos la misma lógica de consulta que /api/dashboard
        sql_pedidos = """
            SELECT p.total_pedido, p.fecha, p.metodo_pago 
            FROM pedidos p 
            WHERE p.fecha >= :fecha_ayer
        """
        sql_productos = """
            SELECT pp.producto, pp.cantidad 
            FROM productos_pedido pp
            JOIN pedidos p ON p.pedido_id = pp.pedido_id
            WHERE p.fecha >= :fecha_inicio_mes
        """
        
        pedidos = fetch_all(sql_pedidos, {"fecha_ayer": fecha_ayer})
        productos = fetch_all(sql_productos, {"fecha_inicio_mes": str(date.today().replace(day=1))})

        # --- El resto de la lógica es idéntica a la del dashboard ---

        def fecha_solo(f):
            return str(f)[:10] if f else ""

        def to_number(v):
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0

        ventas_hoy = sum(to_number(p.get("total_pedido")) for p in pedidos if fecha_solo(p.get("fecha")) == fecha_hoy)
        ventas_ayer = sum(to_number(p.get("total_pedido")) for p in pedidos if fecha_solo(p.get("fecha")) == fecha_ayer)

        productos_vendidos = {}
        for p in productos:
            if p.get("producto"):
                productos_vendidos[p["producto"]] = productos_vendidos.get(p["producto"], 0) + int(p.get("cantidad", 0) or 0)

        producto_mas_vendido = max(productos_vendidos, key=productos_vendidos.get) if productos_vendidos else "N/A"

        metodos_pago = {}
        for p in pedidos:
            metodo = p.get("metodo_pago") or "unknown"
            metodos_pago[metodo] = metodos_pago.get(metodo, 0) + 1

        metodo_pago_mas_usado = max(metodos_pago, key=metodos_pago.get) if metodos_pago else "N/A"

        variacion_porcentaje = ((ventas_hoy - ventas_ayer) / ventas_ayer * 100) if ventas_ayer > 0 else (100 if ventas_hoy > 0 else 0)

        socketio.emit("dashboard_update", {
            "ventas_hoy": ventas_hoy,
            "ventas_ayer": ventas_ayer,
            "producto_mas_vendido": producto_mas_vendido,
            "metodo_pago_mas_usado": metodo_pago_mas_usado,
            "variacion_porcentaje": round(variacion_porcentaje, 2)
        })
    except Exception as e:
        print(f"❌ Error en emitir_dashboard_update: {e}")
