from rest_framework import serializers
from .models import AIModel, Prediction

class AIModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModel
        fields = '__all__'
        read_only_fields = ['user', 'status', 'progress', 'best_model_name', 
                           'model_file_path', 'model_metrics', 'training_time_seconds',
                           'completed_at', 'error_message']

    def validate_csv_source(self, value):
        """Validar que el CSV pertenece al usuario y está procesado"""
        request = self.context['request']
        if value.user != request.user:
            raise serializers.ValidationError("No tienes acceso a este CSV")
        
        if not value.is_ready:
            raise serializers.ValidationError("El CSV no está procesado")
        
        if not value.processed_file:
            raise serializers.ValidationError("El CSV no tiene archivo procesado")
        
        return value

    def validate(self, attrs):
        """Validar que no existe un modelo con el mismo nombre para este usuario"""
        request = self.context['request']
        user = request.user
        name = attrs.get('name')
        
        # Verificar si ya existe un modelo con ese nombre para este usuario
        if AIModel.objects.filter(user=user, name=name).exists():
            raise serializers.ValidationError({
                'name': f'Ya tienes un modelo llamado "{name}". Usa un nombre diferente.'
            })
        
        return attrs

class PredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prediction
        fields = '__all__'
        read_only_fields = ['user']