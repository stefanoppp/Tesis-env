from django.contrib.auth.models import User
from UsersApp.utils import get_redis_connection

def limpiar_tokens_huerfanos():
    redis_conn = get_redis_connection()
    claves = redis_conn.keys("2fa_token:*")

    if not claves:
        return

    for key in claves:
        try:
            user_id = int(key.split(":")[1])
            if not User.objects.filter(id=user_id).exists():
                redis_conn.delete(key)
                print(f"[SYNC] Token huérfano eliminado: {key}")
        except Exception as e:
            print(f"[SYNC] Error procesando {key}: {e}")
