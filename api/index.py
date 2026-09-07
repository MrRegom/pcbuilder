"""
Punto de entrada para el runtime Python de Vercel (@vercel/python).
Vercel empaqueta este archivo como funcion serverless y todas las rutas
(vercel.json) se reenvian aqui; Django resuelve el ruteo real con su propio
URLconf (core/urls.py) como siempre.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

app = get_wsgi_application()
application = app
