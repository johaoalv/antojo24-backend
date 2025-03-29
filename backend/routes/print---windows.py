import win32print
import win32ui

def imprimir_ticket(texto):
    # Obtiene la impresora predeterminada
    impresora = win32print.GetDefaultPrinter()
    
    # Crea un contexto de impresión
    hprinter = win32print.OpenPrinter(impresora)
    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(impresora)

    hdc.StartDoc("Ticket")
    hdc.StartPage()

    # Posición inicial (x, y)
    x = 100
    y = 100

    # Fuente simple
    font = win32ui.CreateFont({
        "name": "Consolas",
        "height": 20,
        "weight": 400
    })
    hdc.SelectObject(font)

    # Escribe línea por línea
    for linea in texto.split('\n'):
        hdc.TextOut(x, y, linea)
        y += 30  # Espacio entre líneas

    hdc.EndPage()
    hdc.EndDoc()
    hdc.DeleteDC()

# Prueba
if __name__ == "__main__":
    ticket = """
    Rapid Food
    -------------
    Hot Dog      $2.00
    Soda         $1.00
    Total:       $3.00
    Gracias por su compra!
    """
    imprimir_ticket(ticket)
