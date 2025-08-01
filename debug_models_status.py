#!/usr/bin/env python
"""
Script de diagnóstico para verificar el estado de los modelos en la base de datos
y identificar problemas con la vista de predicciones.
"""

import os
import sys
import django
from pathlib import Path

# Configurar Django
project_root = Path(__file__).parent
sys.path.append(str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from MLPlatformApp.models import AIModel
from django.contrib.auth.models import User
from django.utils import timezone

def main():
    print("=== DIAGNÓSTICO DE MODELOS ===")
    print(f"Fecha y hora: {timezone.now()}")
    print()
    
    # Contar modelos por estado
    print("📊 RESUMEN POR ESTADO:")
    status_choices = [('pending', 'Pending'), ('training', 'Training'), ('completed', 'Completed'), ('failed', 'Failed')]
    status_counts = {}
    for status_choice in status_choices:
        status = status_choice[0]
        count = AIModel.objects.filter(status=status).count()
        status_counts[status] = count
        print(f"  {status}: {count} modelos")
    
    total_models = AIModel.objects.count()
    print(f"  TOTAL: {total_models} modelos")
    print()
    
    # Modelos por usuario
    print("👥 MODELOS POR USUARIO:")
    users_with_models = User.objects.filter(aimodel__isnull=False).distinct()
    for user in users_with_models:
        user_models = AIModel.objects.filter(user=user)
        completed_count = user_models.filter(status='completed').count()
        total_count = user_models.count()
        print(f"  {user.username}: {completed_count}/{total_count} completados")
        
        # Detalles de modelos no completados
        non_completed = user_models.exclude(status='completed')
        if non_completed.exists():
            print(f"    Modelos no completados:")
            for model in non_completed:
                print(f"      - {model.name} ({model.status}) - {model.created_at}")
    print()
    
    # Verificar modelos con archivos faltantes
    print("📁 VERIFICACIÓN DE ARCHIVOS:")
    completed_models = AIModel.objects.filter(status='completed')
    missing_files = []
    
    for model in completed_models:
        if model.model_path:
            full_path = os.path.join('/app/models', model.model_path)
            if not os.path.exists(full_path):
                missing_files.append(model)
                print(f"  ❌ {model.name} - Archivo faltante: {full_path}")
        else:
            missing_files.append(model)
            print(f"  ❌ {model.name} - Sin ruta de archivo")
    
    if not missing_files:
        print(f"  ✅ Todos los {completed_models.count()} modelos completados tienen archivos válidos")
    else:
        print(f"  ⚠️  {len(missing_files)} modelos con archivos faltantes")
    print()
    
    # Modelos recientes
    print("🕒 MODELOS RECIENTES (últimos 10):")
    recent_models = AIModel.objects.order_by('-created_at')[:10]
    for model in recent_models:
        file_status = "✅" if (model.model_path and os.path.exists(os.path.join('/app/models', model.model_path))) else "❌"
        print(f"  {file_status} {model.name} ({model.status}) - {model.user.username} - {model.created_at}")
    print()
    
    # Recomendaciones
    print("💡 RECOMENDACIONES:")
    if status_counts.get('failed', 0) > 0:
        print(f"  - Hay {status_counts['failed']} modelos fallidos que podrían limpiarse")
    
    if status_counts.get('training', 0) > 0:
        print(f"  - Hay {status_counts['training']} modelos en entrenamiento - verificar si están colgados")
    
    if missing_files:
        print(f"  - {len(missing_files)} modelos completados tienen archivos faltantes")
        print("    Considera ejecutar: python manage.py cleanup_failed_models")
    
    if status_counts.get('completed', 0) == 0:
        print("  - No hay modelos completados disponibles para predicciones")
        print("    Los usuarios necesitan entrenar modelos exitosamente")
    
    print()
    print("=== FIN DEL DIAGNÓSTICO ===")

if __name__ == '__main__':
    main()