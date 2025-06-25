from django.contrib import admin
from .models import AIModel, Prediction

@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'status', 'is_public', 'created_at'] 
    list_filter = ['status', 'is_public', 'created_at']
    search_fields = ['name', 'user__username', 'description']
    readonly_fields = ['created_at', 'completed_at', 'training_time_seconds']

@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ['id', 'ai_model', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['ai_model__name', 'user__username']