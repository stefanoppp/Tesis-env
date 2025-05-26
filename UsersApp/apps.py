# ✅ UsersApp/apps.py
from django.apps import AppConfig

class UsersAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'UsersApp'

    def ready(self):
        from .startup import limpiar_tokens_huerfanos
        limpiar_tokens_huerfanos()
