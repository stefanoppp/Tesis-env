import redis
import json
import random
from django.conf import settings


def get_redis_connection():
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True
    )


def generar_y_guardar_token(user):
    token = f"{random.randint(0, 999999):06d}"
    data = {
        "token": token,
        "intentos": 0
    }
    redis_conn = get_redis_connection()
    redis_conn.setex(
        f'2fa_token:{user.id}',
        settings.REDIS_2FA_EXPIRE_SECONDS,
        json.dumps(data)
    )
    return token
