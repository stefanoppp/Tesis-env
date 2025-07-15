import os
import django

# Configurar Django ANTES de importar modelos
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Configurar Redis para usar localhost
os.environ['REDIS_HOST'] = 'localhost'
os.environ['REDIS_PORT'] = '6379'
os.environ['REDIS_DB'] = '0'

# Configurar Celery para usar localhost
os.environ['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'

django.setup()

# Importar DESPUÉS de configurar Django
from django.contrib.auth.models import User
from UsersApp.tasks import enviar_token_verificacion
from UsersApp.utils import generar_y_guardar_token

def test_celery_email():
    print("=== Prueba de Envío de Email con Celery ===")
    
    try:
        # Buscar un usuario existente o crear uno de prueba
        test_email = "spstefanoperetti17@gmail.com"  # Usar el mismo email configurado
        
        user, created = User.objects.get_or_create(
            username='test_celery_user',
            defaults={
                'email': test_email,
                'first_name': 'Test',
                'last_name': 'Celery',
                'is_active': False
            }
        )
        
        if created:
            print(f"✅ Usuario de prueba creado: {user.username}")
        else:
            print(f"✅ Usuario de prueba encontrado: {user.username}")
        
        # Generar token
        token = generar_y_guardar_token(user)
        print(f"✅ Token generado: {token}")
        
        # Enviar email usando Celery
        print("📧 Enviando email con Celery...")
        result = enviar_token_verificacion.delay(user.id, token)
        print(f"✅ Tarea de Celery enviada con ID: {result.id}")
        
        # Esperar resultado
        print("⏳ Esperando resultado...")
        try:
            result.get(timeout=30)  # Esperar hasta 30 segundos
            print("✅ Email enviado exitosamente a través de Celery")
        except Exception as e:
            print(f"❌ Error en la tarea de Celery: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error general: {e}")
        print(f"Tipo de error: {type(e).__name__}")
        return False

def test_direct_email():
    print("\n=== Prueba de Envío Directo (sin Celery) ===")
    
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from django.template.loader import render_to_string
        
        # Buscar usuario de prueba
        user = User.objects.get(username='test_celery_user')
        token = "123456"  # Token de prueba
        
        context = {
            "first_name": user.first_name,
            "token": token,
            "expire_minutes": settings.REDIS_2FA_EXPIRE_SECONDS // 60
        }
        
        message = render_to_string("emails/verify_token.txt", context)
        
        send_mail(
            subject='Verificación de tu cuenta (Prueba Directa)',
            message=message.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
        
        print("✅ Email enviado directamente (sin Celery)")
        return True
        
    except Exception as e:
        print(f"❌ Error en envío directo: {e}")
        return False

if __name__ == '__main__':
    print("Iniciando pruebas de envío de email...\n")
    
    # Probar envío directo primero
    direct_ok = test_direct_email()
    
    # Probar con Celery
    celery_ok = test_celery_email()
    
    print("\n=== Resumen ===")
    print(f"Envío directo: {'✅ OK' if direct_ok else '❌ FALLO'}")
    print(f"Envío con Celery: {'✅ OK' if celery_ok else '❌ FALLO'}")
    
    if direct_ok and not celery_ok:
        print("\n🔍 El problema está en la configuración de Celery")
    elif not direct_ok and not celery_ok:
        print("\n🔍 El problema está en la configuración de Django/Email")
    elif direct_ok and celery_ok:
        print("\n🎉 Todo funciona correctamente")