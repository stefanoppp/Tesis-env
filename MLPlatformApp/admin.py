from django.contrib import admin
from .models import AIModel, PredictionLog
import os
import logging

logger = logging.getLogger(__name__)

@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'task_type', 'status', 'progress', 'is_public', 'predictions_count', 'created_at']
    list_filter = ['task_type', 'status', 'is_public', 'created_at']
    search_fields = ['name', 'user__username', 'description']
    readonly_fields = ['id', 'created_at', 'progress', 'model_path', 'predictions_count']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'description', 'user', 'task_type', 'is_public')
        }),
        ('Dataset Info', {
            'fields': ('dataset_name', 'target_column', 'features_list')
        }),
        ('Training Status', {
            'fields': ('status', 'progress', 'model_path'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('predictions_count',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def predictions_count(self, obj):
        """Mostrar cantidad de predicciones del modelo"""
        return PredictionLog.objects.filter(ai_model=obj).count()
    predictions_count.short_description = 'Total Predictions'
    
    # ACCIONES PERSONALIZADAS
    actions = ['delete_selected_models_with_files']
    
    def delete_selected_models_with_files(self, request, queryset):
        """Eliminar modelos seleccionados incluyendo archivos físicos"""
        deleted_files = 0
        deleted_models = 0
        
        for ai_model in queryset:
            # Eliminar archivo físico si existe
            if ai_model.model_path and os.path.exists(ai_model.model_path):
                try:
                    os.remove(ai_model.model_path)
                    deleted_files += 1
                    logger.info(f"Deleted model file: {ai_model.model_path}")
                except OSError as e:
                    logger.error(f"Error deleting model file {ai_model.model_path}: {e}")
            
            # Eliminar modelo de BD
            ai_model.delete()
            deleted_models += 1
        
        self.message_user(
            request, 
            f'{deleted_models} models and {deleted_files} files deleted successfully.'
        )
    
    delete_selected_models_with_files.short_description = 'Delete selected models (with files)'
    
    # SOBRESCRIBIR ACCIÓN POR DEFECTO
    def get_actions(self, request):
        actions = super().get_actions(request)
        # Eliminar acción por defecto
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

@admin.register(PredictionLog)
class PredictionLogAdmin(admin.ModelAdmin):
    list_display = ['model_name', 'user', 'is_public_model', 'confidence', 'created_at','model_owner','date_only']
    list_filter = ['is_public_model', 'created_at', 'ai_model__task_type']
    search_fields = ['ai_model__name', 'user__username']
    readonly_fields = ['id', 'created_at', 'prediction_result', 'input_data']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('ai_model', 'user', 'is_public_model', 'confidence')
        }),
        ('Data', {
            'fields': ('input_data', 'prediction_result'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def model_name(self, obj):
        """Mostrar nombre del modelo"""
        return obj.ai_model.name
    model_name.short_description = 'Model Name'
    model_name.admin_order_field = 'ai_model__name'
    def model_owner(self, obj):
        """Mostrar dueño del modelo"""
        return obj.ai_model.user.username
    model_owner.short_description = 'Model Owner'
    model_owner.admin_order_field = 'ai_model__user__username'
    
    def date_only(self, obj):
        """Mostrar solo la fecha para debug"""
        return obj.created_at.date()
    date_only.short_description = 'Date'
    
    # Filtros personalizados
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ai_model', 'user')
    
    # Acciones en lote
    actions = ['delete_selected_predictions']
    
    def delete_selected_predictions(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'{count} predictions deleted successfully.')
    delete_selected_predictions.short_description = 'Delete selected predictions'