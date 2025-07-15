# Script para probar email dentro del contenedor Docker
from django.contrib.auth.models import User
from UsersApp.tasks import enviar_token_verificacion
from UsersApp.utils import generar_y_guardar_token
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

print("=== Prueba de Email en Docker ===")

# Crear o encontrar usuario de prueba
test_email = "spstefanoperetti17@gmail.com"
user, created = User.objects.get_or_create(
    username='test_docker_user',
    defaults={
        'email': test_email,
        'first_name': 'Test',
        'last_name': 'Docker',
        'is_active': False
    }
)

if created:
    print(f"✅ Usuario creado: {user.username}")
else:
    print(f"✅ Usuario encontrado: {user.username}")

# Probar envío directo
print("\n1. Probando envío directo...")
try:
    token = "123456"
    context = {
        "first_name": user.first_name,
        "token": token,
        "expire_minutes": settings.REDIS_2FA_EXPIRE_SECONDS // 60
    }
    
    message = render_to_string("emails/verify_token.txt", context)
    
    send_mail(
        subject='Verificación - Prueba Directa Docker',
        message=message.strip(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
    print("✅ Envío directo exitoso")
except Exception as e:
    print(f"❌ Error en envío directo: {e}")

# Probar con Celery
print("\n2. Probando con Celery...")
try:
    token = generar_y_guardar_token(user)
    print(f"Token generado: {token}")
    
    result = enviar_token_verificacion.delay(user.id, token)
    print(f"Tarea Celery enviada: {result.id}")
    
    # Esperar resultado
    result.get(timeout=30)
    print("✅ Envío con Celery exitoso")
except Exception as e:
    print(f"❌ Error con Celery: {e}")

print("\n=== Fin de pruebas ===")