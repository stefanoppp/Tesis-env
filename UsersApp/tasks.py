from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.conf import settings
from django.template.loader import render_to_string

@shared_task
def enviar_token_verificacion(user_id, token):
    user = User.objects.get(id=user_id)

    context = {
        "first_name": user.first_name,
        "token": token,
        "expire_minutes": settings.REDIS_2FA_EXPIRE_SECONDS // 60
    }

    message = render_to_string("emails/verify_token.txt", context)

    send_mail(
        subject='Verificación de tu cuenta',
        message=message.strip(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
