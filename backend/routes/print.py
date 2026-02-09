from flask import Blueprint, request, jsonify
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import os
import tempfile
import platform
from datetime import datetime

print_bp = Blueprint("print", __name__, url_prefix="/api")

@print_bp.route("/imprimir-ticket", methods=["POST"])
def imprimir_ticket():
    try:
        data = request.json

        pedido = data.get("pedido", [])
        total_pedido = data.get("total_pedido", 0.00)
        metodo_pago = data.get("metodo_pago", "N/A")
        nombre_cliente = data.get("nombre_cliente", "")
        pedido_id = pedido[0].get("pedido_id", "N/A") if pedido else "N/A"

        # Tamaño de papel térmico: 58mm de ancho, largo flexible
        width = 58 * mm
        height = max(80, (len(pedido) + 8) * 10) * mm  # altura dinámica

        # Crear PDF temporal
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        c = canvas.Canvas(temp_file.name, pagesize=(width, height))

        x = 5
        y = height - 20

        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(width / 2, y, "RAPID FOOD")
        y -= 15
        
        # Agregar nombre del cliente si existe
        if nombre_cliente:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(x, y, f"Cliente: {nombre_cliente}")
            y -= 12
        
        c.setFont("Helvetica", 8)
        c.drawString(x, y, f"Pedido ID: {pedido_id}")
        y -= 12
        c.drawString(x, y, datetime.now().strftime("%Y-%m-%d %H:%M"))
        y -= 12
        c.drawString(x, y, "-" * 32)
        y -= 12

        for item in pedido:
            cantidad = item.get("cantidad", 1)
            producto = item.get("producto", "")
            total_item = item.get("total_item", 0.00)
            linea = f"{cantidad}x {producto[:15]:<15} ${total_item:>5.2f}"
            c.drawString(x, y, linea)
            y -= 12

        y -= 5
        c.drawString(x, y, "-" * 32)
        y -= 12
        c.drawString(x, y, f"Método de pago: {metodo_pago}")
        y -= 12
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x, y, f"TOTAL: ${total_pedido:.2f}")
        y -= 18
        c.setFont("Helvetica", 9)
        c.drawCentredString(width / 2, y, "Gracias por su compra :3")
        y -= 12
        c.setFont("Helvetica", 8)
        c.drawCentredString(width / 2, y, "@antojo24.pa")

        c.showPage()
        c.save()

        # Imprimir
        if platform.system() == "Darwin":  # macOS
            os.system(f"lp '{temp_file.name}'")
        elif platform.system() == "Windows":
            os.startfile(temp_file.name, "print")
        else:
            return jsonify({"status": "error", "message": "Sistema no soportado"}), 500

        return jsonify({"status": "success", "message": "Ticket generado e impreso"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
