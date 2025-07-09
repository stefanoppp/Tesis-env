#!/usr/bin/env python
"""
Script de prueba para verificar la eliminación correcta de archivos físicos
en operaciones de bulk delete.

Uso:
1. Crear algunos modelos de prueba con archivos
2. Ejecutar eliminación múltiple
3. Verificar que los archivos fueron eliminados

python test_bulk_delete_files.py
"""

import os
import django
import sys

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.append('/path/to/your/django/project')  # Ajustar path
django.setup()

from django.contrib.auth.models import User
from MLPlatformApp.models import AIModel
import tempfile
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_files():
    """Crear archivos de prueba y modelos asociados"""
    # Obtener o crear usuario de prueba
    user, created = User.objects.get_or_create(
        username='test_bulk_delete',
        defaults={'email': 'test@example.com'}
    )
    
    # Crear directorio temporal para archivos de prueba
    test_dir = tempfile.mkdtemp(prefix='modelium_test_')
    logger.info(f"Created test directory: {test_dir}")
    
    models_created = []
    files_created = []
    
    # Crear 3 modelos de prueba con archivos físicos
    for i in range(3):
        # Crear archivo físico de prueba
        file_path = os.path.join(test_dir, f'test_model_{i}.pkl')
        with open(file_path, 'w') as f:
            f.write(f'Fake model content for model {i}')
        files_created.append(file_path)
        
        # Crear modelo en BD
        model = AIModel.objects.create(
            user=user,
            name=f'Test Model {i}',
            description=f'Test model for bulk delete {i}',
            task_type='classification',
            target_column='target',
            dataset_name=f'test_dataset_{i}.csv',
            model_path=file_path,
            status='completed'
        )
        models_created.append(model)
        logger.info(f"Created model {model.name} with file {file_path}")
    
    return user, models_created, files_created

def test_bulk_delete():
    """Probar eliminación múltiple y verificar archivos"""
    logger.info("=== INICIANDO PRUEBA DE BULK DELETE ===")
    
    # 1. Crear modelos y archivos de prueba
    user, models, files = create_test_files()
    model_ids = [str(model.id) for model in models]
    
    # 2. Verificar que archivos existen antes de eliminación
    logger.info("Verificando archivos antes de eliminación:")
    files_exist_before = []
    for file_path in files:
        exists = os.path.exists(file_path)
        files_exist_before.append(exists)
        logger.info(f"  {file_path}: {'EXISTS' if exists else 'NOT FOUND'}")
    
    # 3. Simular request de eliminación múltiple
    from MLPlatformApp.views import DeleteMultipleModelsView
    
    view = DeleteMultipleModelsView()
    
    # Simular queryset de modelos a eliminar
    models_to_delete = AIModel.objects.filter(id__in=model_ids, user=user)
    logger.info(f"Models to delete: {models_to_delete.count()}")
    
    # 4. Ejecutar eliminación de archivos (método helper)
    files_cleanup_result = view._delete_model_files(models_to_delete)
    logger.info(f"Files cleanup result: {files_cleanup_result}")
    
    # 5. Eliminar modelos de BD
    deleted_count = models_to_delete.count()
    models_to_delete.delete()
    logger.info(f"Deleted {deleted_count} models from database")
    
    # 6. Verificar que archivos fueron eliminados
    logger.info("Verificando archivos después de eliminación:")
    files_exist_after = []
    for file_path in files:
        exists = os.path.exists(file_path)
        files_exist_after.append(exists)
        logger.info(f"  {file_path}: {'EXISTS' if exists else 'DELETED'}")
    
    # 7. Evaluar resultados
    logger.info("=== RESULTADOS DE LA PRUEBA ===")
    logger.info(f"Archivos antes: {sum(files_exist_before)}/{len(files)}")
    logger.info(f"Archivos después: {sum(files_exist_after)}/{len(files)}")
    logger.info(f"Archivos eliminados exitosamente: {files_cleanup_result['files_deleted']}")
    logger.info(f"Archivos con error: {files_cleanup_result['files_failed']}")
    
    # 8. Verificar que la prueba fue exitosa
    success = (
        sum(files_exist_before) == len(files) and  # Todos existían antes
        sum(files_exist_after) == 0 and           # Ninguno existe después
        files_cleanup_result['files_failed'] == 0  # No hubo errores
    )
    
    if success:
        logger.info("✅ PRUEBA EXITOSA: Todos los archivos fueron eliminados correctamente")
    else:
        logger.error("❌ PRUEBA FALLIDA: Algunos archivos no fueron eliminados")
        if files_cleanup_result['files_failed'] > 0:
            logger.error(f"Errores: {files_cleanup_result['failed_files']}")
    
    # 9. Limpiar usuario de prueba
    user.delete()
    logger.info("Cleaned up test user")
    
    return success

if __name__ == '__main__':
    try:
        success = test_bulk_delete()
        exit_code = 0 if success else 1
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Error durante la prueba: {e}")
        sys.exit(1)
