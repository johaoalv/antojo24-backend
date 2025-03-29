from flask import Blueprint, request, jsonify
import win32print
import win32ui
from datetime import datetime

print_bp = Blueprint("print", __name__, url_prefix="/api" )

@print_bp.route("/imprimir-ticket", methods=["POST"])
def imprimir_ticket():

    try:
        data = request.json

        pedido = data.get("pedido", [])
        if not pedido:
            return jsonify({"status": "error", "message": "No se recibieron productos"}), 400

        total_pedido = pedido[0].get("total_pedido", 0.00)
        metodo_pago = pedido[0].get("metodo_pago", "N/A")
        pedido_id = pedido[0].get("pedido_id", "N/A")


        # Setup de impresion
        impresora = win32print.GetDefaultPrinter()
        hprinter = win32print.OpenPrinter(impresora)
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(impresora)

        hdc.StartDoc("Ticket ESC/POS")
        hdc.StartPage()

        x = 20
        y = 100

        # Simulamos un ESC/POS visual (consolas es monoespaciado)
        font = win32ui.CreateFont({
            "name": "Consolas",
            "height": 30,  # más grande
            "weight": 700  # negrita
        })
        hdc.SelectObject(font)

        hdc.TextOut(x, y, "RAPID FOOD")
        y += 40
        hdc.TextOut(x, y, f"Pedido ID: {pedido_id}")
        y += 40
        hdc.TextOut(x, y, datetime.now().strftime("%Y-%m-%d %H:%M"))
        y += 40
        hdc.TextOut(x, y, "------------------------")
        y += 30

        for item in pedido:
            cantidad = item.get("cantidad", 1)
            producto = item.get("producto", "")
            total_item = item.get("total_item", 0.00)
            linea = f"{cantidad}x {producto:<12} ${total_item:>5.2f}"
            hdc.TextOut(x, y, linea)
            y += 30

        # Total y cierre
        y += 20
        hdc.TextOut(x, y, f"Método: {metodo_pago}")
        y += 30
        hdc.TextOut(x, y, f"Total:            ${total_pedido:.2f}")
        y += 30
        hdc.TextOut(x, y, "--------------------------")
        y += 40
        hdc.TextOut(x, y, "Gracias por su compra!")

        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()

        return jsonify({"status": "success", "message": "Ticket impreso"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500