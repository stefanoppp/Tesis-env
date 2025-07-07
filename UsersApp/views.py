import json
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import timedelta
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
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        })


class SessionExtendView(APIView):
    """
    Vista para extender la sesión del usuario basada en actividad.
    Renueva el access token si el usuario está activo.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # Verificar que el usuario esté autenticado
            user = request.user
            
            # Actualizar el último login para tracking de actividad
            update_last_login(None, user)
            
            # Generar nuevo token de acceso
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'message': 'Sesión extendida exitosamente',
                'access': str(refresh.access_token),
                'user_activity': {
                    'last_activity': timezone.now(),
                    'session_extended': True
                }
            }, status=200)
            
        except Exception as e:
            return Response({
                'error': 'Error al extender sesión',
                'detail': str(e)
            }, status=400)


class ActivityHeartbeatView(APIView):
    """
    Vista para recibir el heartbeat de actividad del usuario.
    Se llama periódicamente desde el frontend para mantener la sesión activa.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            user = request.user
            
            # Registrar actividad del usuario
            redis_conn = get_redis_connection()
            activity_key = f'user_activity:{user.id}'
            
            # Guardar timestamp de última actividad
            activity_data = {
                'last_activity': timezone.now().isoformat(),
                'user_id': user.id,
                'session_active': True
            }
            
            # Guardar en Redis con expiración de 20 minutos (más que el timeout de 15 min)
            redis_conn.setex(
                activity_key,
                20 * 60,  # 20 minutos en segundos
                json.dumps(activity_data)
            )
            
            return Response({
                'status': 'activity_recorded',
                'last_activity': timezone.now(),
                'session_status': 'active'
            }, status=200)
            
        except Exception as e:
            return Response({
                'error': 'Error al registrar actividad',
                'detail': str(e)
            }, status=400)


class SessionStatusView(APIView):
    """
    Vista para verificar el estado de la sesión del usuario.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            user = request.user
            redis_conn = get_redis_connection()
            activity_key = f'user_activity:{user.id}'
            
            # Verificar última actividad
            activity_data_raw = redis_conn.get(activity_key)
            
            if activity_data_raw:
                activity_data = json.loads(activity_data_raw)
                last_activity = timezone.datetime.fromisoformat(activity_data['last_activity'])
                time_since_activity = timezone.now() - last_activity
                
                # Verificar si la sesión debe expirar (15 minutos de inactividad)
                session_timeout = timedelta(minutes=15)
                session_expired = time_since_activity > session_timeout
                
                return Response({
                    'session_active': not session_expired,
                    'last_activity': last_activity,
                    'time_since_activity_seconds': int(time_since_activity.total_seconds()),
                    'session_timeout_seconds': int(session_timeout.total_seconds()),
                    'user': {
                        'id': user.id,
                        'username': user.username
                    }
                }, status=200)
            else:
                return Response({
                    'session_active': False,
                    'message': 'No activity data found'
                }, status=200)
                
        except Exception as e:
            return Response({
                'error': 'Error al verificar estado de sesión',
                'detail': str(e)
            }, status=400)


class CustomTokenRefreshView(TokenRefreshView):
    """
    Vista personalizada para refresh de tokens que también registra actividad.
    """
    
    def post(self, request, *args, **kwargs):
        try:
            # Llamar al método padre para hacer el refresh normal
            response = super().post(request, *args, **kwargs)
            
            if response.status_code == 200:
                # Si el refresh fue exitoso, obtener el usuario y registrar actividad
                refresh_token = request.data.get('refresh')
                if refresh_token:
                    try:
                        token = RefreshToken(refresh_token)
                        user_id = token.payload.get('user_id')
                        if user_id:
                            user = User.objects.get(id=user_id)
                            update_last_login(None, user)
                            
                            # Registrar actividad en Redis
                            redis_conn = get_redis_connection()
                            activity_key = f'user_activity:{user.id}'
                            activity_data = {
                                'last_activity': timezone.now().isoformat(),
                                'user_id': user.id,
                                'session_active': True,
                                'token_refreshed': True
                            }
                            redis_conn.setex(activity_key, 20 * 60, json.dumps(activity_data))
                            
                    except (TokenError, User.DoesNotExist):
                        pass  # Si hay error, continuar con el response normal
            
            return response
            
        except Exception as e:
            return Response({
                'error': 'Error al renovar token',
                'detail': str(e)
            }, status=400)