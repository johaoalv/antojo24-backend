import requests
import json

def migrate():
    try:
        with open(r'c:\Users\antojo\Documents\GitHub\antojo24-frontend\frontend\src\api\productos.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print(f"Encontrados {len(data)} productos. Enviando al backend...")
        
        # Migramos enviando la data al endpoint especial
        response = requests.post("http://127.0.0.1:5000/api/productos/migrar", json=data)
        
        if response.status_code == 200:
            print(f"Exito: {response.json()}")
        else:
            print(f"Error ({response.status_code}): {response.text}")
            
    except Exception as e:
        print(f"Error al leer/enviar: {e}")

if __name__ == "__main__":
    migrate()
