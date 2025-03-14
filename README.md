# Backend - Rapid Food

Este documento proporciona los pasos necesarios para configurar y ejecutar el backend del proyecto **Rapid Food** en tu entorno local.

## Tecnologías utilizadas
- **Backend:** Python
- **Base de Datos:** Supabase (gestionada desde n8n)
- **Control de versiones:** GitHub

## Requisitos previos
Antes de comenzar, asegúrate de tener instalados los siguientes componentes:

- **Python 3.10+**: [Descargar e instalar](https://www.python.org/downloads/)
- **Git**: [Descargar e instalar](https://git-scm.com/downloads)

## Instalación
1. **Clonar el repositorio:**
   ```sh
   git clone https://github.com/tu_usuario/rapid-food-backend.git
   cd rapid-food-backend
   ```

2. **Crear y activar un entorno virtual:**
   ```sh
   python -m venv env
   source env/bin/activate  # En macOS/Linux
   env\Scripts\activate  # En Windows
   venv\Scripts\Activate

   ```

3. **Instalar las dependencias:**
   ```sh
   pip install -r requirements.txt
   ```

## Configuración
1. **Crear un archivo `.env` en la raíz del proyecto y agregar las siguientes variables:**
   ```ini
   N8N_API_KEY=tu-api-key-de-n8n
   N8N_WEBHOOK_URLL=https://tu-n8n-url.com
   FRONTEND_URL=http://localhost:5173



## Ejecución del backend
Para iniciar el servidor localmente:
```sh
cd backend
python app.py
```
El backend estará disponible en `http://127.0.0.1:5000/`.


## Despliegue
El backend se despliega en **Railway**. Puedes verlo en:
[https://rapid-food-backend.railway.app](https://rapid-food-backend.railway.app)

## Contacto
Si tienes dudas o mejoras, abre un issue en GitHub o contáctame.

