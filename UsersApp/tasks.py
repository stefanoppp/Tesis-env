from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.conf import settings
from django.template.loader import render_to_string

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
