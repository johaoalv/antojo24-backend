import requests
r = requests.get('http://localhost:5000/api/insumos')
for i in r.json():
    print(f"{i['nombre']}: {i['stock']}")
