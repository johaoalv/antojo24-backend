import requests
try:
    r = requests.get('http://localhost:5000/api/dashboard')
    data = r.json()
    print("--- Dashboard API Response ---")
    for k, v in data.items():
        print(f"{k}: {v}")
except Exception as e:
    print(f"Error: {e}")
