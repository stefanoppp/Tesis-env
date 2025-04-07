from rest_framework import serializers
from django.contrib.auth.models import User
from UsersApp.tasks import enviar_token_verificacion
from .utils import get_redis_connection

# Serializador de registro
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user  # ✅ NO LLAMES A NADA MÁS ACÁ

# Serializador de verificacion
class VerifyTokenSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField()

    def validate(self, data):
        email = data['email']
        token = data['token']
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Usuario no encontrado")

        redis_conn = get_redis_connection()
        key = f'2fa_token:{user.id}'
        token_almacenado = redis_conn.get(key)

        if token_almacenado is None:
            raise serializers.ValidationError("El token expiró o no existe")
        if token != token_almacenado:
            raise serializers.ValidationError("Token inválido")

        # Marcamos como verificado (p.ej. usando is_active)
        user.is_active = True
        user.save()
        redis_conn.delete(key)
        return data
