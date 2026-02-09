import requests
from datetime import datetime

pedido = {
    "pedido_id": "test-stock-fail",
    "pedido": [
        {"producto": "soda", "cantidad": 5, "total_item": 7.5, "pedido_id": "test-stock-fail"}
    ],
    "total_pedido": 7.5,
    "metodo_pago": "tarjeta",
    "fecha": datetime.now().isoformat(),
    "sucursal_id": "sucursal_1"
}

r = requests.post('http://localhost:5000/api/pedido', json=pedido)
print(f"Status Code: {r.status_code}")
print(f"Response Body: {r.json()}")
