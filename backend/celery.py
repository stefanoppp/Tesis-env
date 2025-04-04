import os
from celery import Celery

# Establece el archivo de settings por defecto para comandos de celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Crea la instancia de la app Celery
app = Celery('backend')

# Carga la configuración desde settings.py, usando el prefijo CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscovery de tareas en todas las apps instaladas
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
