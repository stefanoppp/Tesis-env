#!/usr/bin/env python
"""
Script de prueba para las tareas de Celery Beat
Ejecuta manualmente las tareas para verificar que funcionan correctamente
"""

import os
import django
from django.conf import settings

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from UsersApp.tasks import cleanup_failed_models, detect_stuck_models
from MLPlatformApp.models import AIModel
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

def create_test_data():
    """Crear datos de prueba para las tareas"""
    print("🔧 Creando datos de prueba...")
    
    # Crear usuario de prueba si no existe
    user, created = User.objects.get_or_create(
        username='test_user',
        defaults={'email': 'test@example.com', 'first_name': 'Test'}
    )
    
    # Crear modelo fallido antiguo (más de 7 días)
    old_failed_model = AIModel.objects.create(
        name='Modelo Fallido Antiguo',
        user=user,
        status='failed',
        task_type='classification',
        error_message='Error de prueba'
    )
    # Simular que fue creado hace 8 días
    old_failed_model.created_at = timezone.now() - timedelta(days=8)
    old_failed_model.save()
    
    # Crear modelo colgado (en training por más de 2 horas)
    stuck_model = AIModel.objects.create(
        name='Modelo Colgado',
        user=user,
        status='training',
        task_type='regression'
    )
    # Simular que fue actualizado hace 3 horas
    stuck_model.updated_at = timezone.now() - timedelta(hours=3)
    stuck_model.save()
    
    # Crear modelo fallido reciente (no debe eliminarse)
    recent_failed_model = AIModel.objects.create(
        name='Modelo Fallido Reciente',
        user=user,
        status='failed',
        task_type='classification',
        error_message='Error reciente'
    )
    
    # Crear modelo en training normal (no debe marcarse como colgado)
    normal_model = AIModel.objects.create(
        name='Modelo Normal',
        user=user,
        status='training',
        task_type='classification'
    )
    
    print(f"✅ Datos de prueba creados:")
    print(f"   • Modelo fallido antiguo: {old_failed_model.id}")
    print(f"   • Modelo colgado: {stuck_model.id}")
    print(f"   • Modelo fallido reciente: {recent_failed_model.id}")
    print(f"   • Modelo normal: {normal_model.id}")
    
    return old_failed_model, stuck_model, recent_failed_model, normal_model

def test_cleanup_task():
    """Probar la tarea de limpieza de modelos fallidos"""
    print("\n🧹 Probando tarea de limpieza de modelos fallidos...")
    
    # Contar modelos antes
    failed_count_before = AIModel.objects.filter(status='failed').count()
    print(f"   Modelos fallidos antes: {failed_count_before}")
    
    # Ejecutar tarea
    result = cleanup_failed_models.delay()
    result_value = result.get()
    
    # Contar modelos después
    failed_count_after = AIModel.objects.filter(status='failed').count()
    print(f"   Modelos fallidos después: {failed_count_after}")
    print(f"   Resultado: {result_value}")
    
    return result_value

def test_stuck_detection_task():
    """Probar la tarea de detección de modelos colgados"""
    print("\n🔍 Probando tarea de detección de modelos colgados...")
    
    # Contar modelos en training antes
    training_count_before = AIModel.objects.filter(status='training').count()
    print(f"   Modelos en training antes: {training_count_before}")
    
    # Ejecutar tarea
    result = detect_stuck_models.delay()
    result_value = result.get()
    
    # Contar modelos después
    training_count_after = AIModel.objects.filter(status='training').count()
    failed_count_after = AIModel.objects.filter(status='failed').count()
    print(f"   Modelos en training después: {training_count_after}")
    print(f"   Modelos fallidos después: {failed_count_after}")
    print(f"   Resultado: {result_value}")
    
    return result_value

def cleanup_test_data():
    """Limpiar datos de prueba"""
    print("\n🗑️  Limpiando datos de prueba...")
    AIModel.objects.filter(name__contains='Modelo').delete()
    User.objects.filter(username='test_user').delete()
    print("✅ Datos de prueba eliminados")

if __name__ == '__main__':
    print("🚀 INICIANDO PRUEBAS DE CELERY BEAT TASKS")
    print("=" * 50)
    
    try:
        # Crear datos de prueba
        test_models = create_test_data()
        
        # Probar tareas
        cleanup_result = test_cleanup_task()
        stuck_result = test_stuck_detection_task()
        
        print("\n" + "=" * 50)
        print("🎉 PRUEBAS COMPLETADAS EXITOSAMENTE")
        print(f"   • Limpieza: {cleanup_result}")
        print(f"   • Detección: {stuck_result}")
        
    except Exception as e:
        print(f"\n❌ ERROR EN LAS PRUEBAS: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Limpiar datos de prueba
        cleanup_test_data()
        print("\n✅ Pruebas finalizadas")