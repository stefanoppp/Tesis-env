from django.db import models
from django.contrib.auth.models import User
from PreprocessingApp.models import CSVModel
from django.utils import timezone
import os
import shutil

class AIModel(models.Model):
    TASK_CHOICES = [
        ('classification', 'Clasificación'),
        ('regression', 'Regresión'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('training', 'Entrenando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    csv_source = models.ForeignKey(CSVModel, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    # Configuración
    is_public = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.IntegerField(default=0)
    
    # Resultados del entrenamiento (se llenan después)
    best_model_name = models.CharField(max_length=100, blank=True)
    model_file_path = models.CharField(max_length=500, blank=True)
    model_metrics = models.JSONField(default=dict, blank=True)
    
    # Metadatos
    training_time_seconds = models.FloatField(null=True, blank=True)
    dataset_size = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'name']
        
    def __str__(self):
        return f"{self.name} ({self.user.username})"

class Prediction(models.Model):
    ai_model = models.ForeignKey(AIModel, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    input_data = models.JSONField()
    prediction_result = models.JSONField(default=dict, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Predicción {self.id} - {self.ai_model.name}"
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Predicción {self.id} - {self.ai_model.name}"