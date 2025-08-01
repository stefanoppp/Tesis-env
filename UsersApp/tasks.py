from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.conf import settings
from django.template.loader import render_to_string
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

def enviar_token_verificacion(user_id, token):
    print(f"[EMAIL DEBUG] Entrando a enviar_token_verificacion con user_id={user_id}, token={token}")
    user = User.objects.get(id=user_id)

    context = {
        "first_name": user.first_name,
        "token": token,
        "expire_minutes": settings.REDIS_2FA_EXPIRE_SECONDS // 60
    }

    message = render_to_string("emails/verify_token.txt", context)

    try:
        result = send_mail(
            subject='Verificación de tu cuenta',
            message=message.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
        print(f"[EMAIL DEBUG] Email enviado a {user.email}, resultado send_mail: {result}")
    except Exception as e:
        import traceback
        print(f"[EMAIL ERROR] Falló el envío de email a {user.email}: {e}")
        traceback.print_exc()


@shared_task
def cleanup_failed_models():
    """Tarea automática para limpiar modelos fallidos antiguos"""
    from MLPlatformApp.models import AIModel
    
    # Obtener umbral de días desde settings (por defecto 7 días)
    cleanup_days = getattr(settings, 'CLEANUP_FAILED_MODELS_DAYS', 7)
    cutoff_date = timezone.now() - timedelta(days=cleanup_days)
    
    # Buscar modelos fallidos antiguos
    failed_models = AIModel.objects.filter(
        status='failed',
        created_at__lt=cutoff_date
    )
    
    count = failed_models.count()
    if count > 0:
        # Eliminar modelos fallidos
        failed_models.delete()
        logger.info(f"Limpieza automática: {count} modelos fallidos eliminados (más de {cleanup_days} días)")
    else:
        logger.info(f"Limpieza automática: No hay modelos fallidos para eliminar (umbral: {cleanup_days} días)")
    
    return f"Modelos fallidos eliminados: {count}"


@shared_task
def detect_stuck_models():
    """Tarea automática para detectar y marcar modelos colgados en entrenamiento"""
    from MLPlatformApp.models import AIModel
    
    # Modelos en entrenamiento por más de 2 horas se consideran colgados
    stuck_threshold = timezone.now() - timedelta(hours=2)
    
    # Buscar modelos en estado 'training' por mucho tiempo
    stuck_models = AIModel.objects.filter(
        status='training',
        updated_at__lt=stuck_threshold
    )
    
    count = 0
    for model in stuck_models:
        model.status = 'failed'
        model.error_message = 'Entrenamiento interrumpido - modelo colgado detectado automáticamente'
        model.save()
        count += 1
        logger.warning(f"Modelo colgado detectado y marcado como fallido: {model.id} - {model.name}")
    
    if count > 0:
        logger.info(f"Detección automática: {count} modelos colgados marcados como fallidos")
    else:
        logger.info("Detección automática: No se encontraron modelos colgados")
    
    return f"Modelos colgados detectados: {count}"
