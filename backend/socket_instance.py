# socket_instance.py
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import os

load_dotenv()
allowed_origins = [os.getenv("NETLIFY_URL"), "http://localhost:5173"]
socketio = SocketIO(cors_allowed_origins=allowed_origins)
