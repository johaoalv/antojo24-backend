# utils/emit_stock_alerts.py

from socket_instance import socketio
from db import fetch_all, execute


def emitir_stock_alerts():
    """
    Verifica insumos con stock <= stock_minimo y emite alerta por WebSocket.
    Solo emite insumos que NO han sido marcados como 'alerta_vista'.
    """
    try:
        sql = """
            SELECT id, nombre, stock, stock_minimo, unidad_medida, costo_unidad
            FROM insumos
            WHERE stock_minimo > 0
              AND stock <= stock_minimo
              AND alerta_vista = FALSE
            ORDER BY stock ASC
        """
        insumos_bajos = fetch_all(sql)

        if insumos_bajos:
            alertas = []
            for insumo in insumos_bajos:
                stock = float(insumo["stock"] or 0)
                minimo = float(insumo["stock_minimo"] or 0)

                # Determinar severidad
                if stock <= 0:
                    nivel = "critico"
                elif stock <= minimo * 0.5:
                    nivel = "alto"
                else:
                    nivel = "bajo"

                alertas.append({
                    "id": insumo["id"],
                    "nombre": insumo["nombre"],
                    "stock": stock,
                    "stock_minimo": minimo,
                    "unidad_medida": insumo["unidad_medida"],
                    "nivel": nivel
                })

            socketio.emit("stock_alert", {"alertas": alertas})

    except Exception as e:
        print(f"❌ Error en emitir_stock_alerts: {e}")


def resetear_alerta_por_stock(insumo_id):
    """
    Resetea alerta_vista a FALSE cuando el stock de un insumo cambia.
    Así si vuelve a bajar, la alerta aparece de nuevo.
    """
    try:
        execute(
            "UPDATE insumos SET alerta_vista = FALSE WHERE id = :id",
            {"id": insumo_id}
        )
    except Exception as e:
        print(f"❌ Error al resetear alerta: {e}")
