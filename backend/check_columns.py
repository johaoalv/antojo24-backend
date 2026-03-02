from dotenv import load_dotenv
load_dotenv()
from db import fetch_all
print(fetch_all("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'pedidos'"))
