import json
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from UsersApp.serializers import RegisterSerializer
from UsersApp.tasks import enviar_token_verificacion
from UsersApp.utils import get_redis_connection, generar_y_guardar_token
from django.contrib.auth.models import update_last_login

class RegisterView(APIView):
    def post(self, request):
        email = request.data.get('email')
        username = request.data.get('username')

        # Verificar si ya existe el username
        if User.objects.filter(username=username).exists():
            return Response({'error': 'Este nombre de usuario ya está en uso.'}, status=400)

        # Verificar si ya existe el email
        if User.objects.filter(email=email).exists():
            return Response({'error': 'Este correo ya está registrado.'}, status=400)

        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            response = {'message': 'Usuario creado correctamente. Verificá tu correo.'}

            token = generar_y_guardar_token(user)
            if settings.USE_CELERY_FOR_2FA:
                enviar_token_verificacion.delay(user.id, token)
            if settings.DEBUG:
                response['dev_token'] = token

            return Response(response, status=201)

        return Response(serializer.errors, status=400)


class VerifyTokenView(APIView):
    def post(self, request):
        username = request.data.get('username')
        token_ingresado = str(request.data.get('token'))

        if not username or not token_ingresado:
            return Response({'error': 'Faltan credenciales'}, status=400)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=404)

        redis_conn = get_redis_connection()
        key = f'2fa_token:{user.id}'
        data_raw = redis_conn.get(key)

        if not data_raw:
            return Response({'error': 'Token expirado o inválido'}, status=400)

        data = json.loads(data_raw)

        if data["token"] == token_ingresado:
            user.is_active = True
            user.save()
            redis_conn.delete(key)
            return Response({'message': 'Usuario verificado con éxito'}, status=200)

        # Token incorrecto
        data["intentos"] += 1

        if data["intentos"] >= settings.REDIS_2FA_MAX_ATTEMPTS:
            redis_conn.delete(key)
            return Response({'error': 'Demasiados intentos. Token inválido.'}, status=403)
        else:
            # Solo se guarda si aún no se superó el límite
            redis_conn.setex(
                key,
                settings.REDIS_2FA_EXPIRE_SECONDS,
                json.dumps(data)
            )
            return Response({
                'error': 'Token incorrecto',
                'intentos_restantes': settings.REDIS_2FA_MAX_ATTEMPTS - data["intentos"]
            }, status=400)


class LoginView(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(username=username, password=password)

        if user is None:
            # Verificamos si existe pero está inactivo
            try:
                user_obj = User.objects.get(username=username)
                if not user_obj.is_active:
                    return Response({'error': 'Usuario no verificado'}, status=403)
            except User.DoesNotExist:
                pass
            return Response({'error': 'Credenciales inválidas'}, status=401)
        
        update_last_login(None, user)
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })