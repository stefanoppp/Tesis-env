from django.db import models
from django.contrib.auth.models import User
import uuid
import os
import logging
class AIModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Info básica
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=[
        ('classification', 'Classification'),
        ('regression', 'Regression')
    ])
    # Metricas. Inicialmente vacío, se llenará al completar el entrenamiento
    model_metrics = models.JSONField(default=dict, blank=True)
    # Metadatos del dataset (sin almacenar archivo)
    dataset_name = models.CharField(max_length=200)
    target_column = models.CharField(max_length=100)
    features_list = models.JSONField(default=list)  # Lista de características
    
    # Estado
    status = models.CharField(max_length=20, default='training', choices=[
        ('training', 'Training'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ])
    progress = models.IntegerField(default=0)
    
    # Archivos del modelo
    model_path = models.CharField(max_length=500, blank=True)
    
    # Marketplace
    is_public = models.BooleanField(default=False)    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Remover unique_together para manejarlo manualmente
        ordering = ['-created_at']
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        if self.is_public:
            # Para modelos públicos: nombre único globalmente
            if AIModel.objects.filter(name=self.name, is_public=True).exclude(id=self.id).exists():
                raise ValidationError(f'A public model with name "{self.name}" already exists')
        else:
            # Para modelos privados: nombre único por usuario
            if AIModel.objects.filter(user=self.user, name=self.name).exclude(id=self.id).exists():
                raise ValidationError(f'You already have a model named "{self.name}"')
    def delete(self, *args, **kwargs):
        """Eliminar archivo físico del modelo al borrar registro"""
        if self.model_path and os.path.exists(self.model_path):
            try:
                os.remove(self.model_path)
                logging.info(f"Deleted model file: {self.model_path}")
            except OSError as e:
                logging.error(f"Error deleting model file {self.model_path}: {e}")
        
        super().delete(*args, **kwargs)
# Agregar al final del archivo models.py

class PredictionLog(models.Model):
    """Log de predicciones para tracking y rate limiting"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ai_model = models.ForeignKey(AIModel, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    input_data = models.JSONField()
    prediction_result = models.JSONField()
    confidence = models.FloatField(null=True, blank=True)
    
    # Para tracking
    is_public_model = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ai_model', 'user', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"Prediction by {self.user.username} on {self.ai_model.name}"