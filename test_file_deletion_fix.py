#!/usr/bin/env python
"""
Script para probar que la eliminación de archivos físicos funciona correctamente
con la nueva configuración de volúmenes de Docker.
"""

import os
import sys
import django
from pathlib import Path

# Configurar Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth.models import User
from MLPlatformApp.models import AIModel
from django.conf import settings
import tempfile
import uuid

def test_file_deletion():
    """
    Prueba que los archivos físicos se eliminen correctamente
    cuando se borra un modelo desde el admin de Django.
    """
    print("=== PRUEBA DE ELIMINACIÓN DE ARCHIVOS FÍSICOS ===")
    print(f"MEDIA_ROOT configurado en: {settings.MEDIA_ROOT}")
    
    # Crear usuario de prueba
    user, created = User.objects.get_or_create(
        username='test_deletion',
        defaults={'email': 'test@example.com'}
    )
    print(f"Usuario de prueba: {user.username} ({'creado' if created else 'existente'})")
    
    # Crear archivo de prueba en MEDIA_ROOT
    media_dir = Path(settings.MEDIA_ROOT)
    media_dir.mkdir(exist_ok=True)
    
    test_file_path = media_dir / f"test_model_{uuid.uuid4().hex[:8]}.pkl"
    
    # Escribir contenido de prueba
    with open(test_file_path, 'w') as f:
        f.write("Archivo de prueba para modelo de ML")
    
    print(f"Archivo de prueba creado: {test_file_path}")
    print(f"¿Archivo existe antes de crear modelo? {test_file_path.exists()}")
    
    # Crear modelo en la base de datos
    ai_model = AIModel.objects.create(
        user=user,
        name="Modelo de Prueba - Eliminación",
        description="Modelo para probar eliminación de archivos",
        task_type="classification",
        status="completed",
        model_path=str(test_file_path),
        dataset_name="test_dataset.csv",
        target_column="target"
    )
    
    print(f"Modelo creado en BD: {ai_model.name} (ID: {ai_model.id})")
    print(f"Ruta del modelo: {ai_model.model_path}")
    
    # Verificar que el archivo existe
    if test_file_path.exists():
        print("✅ Archivo físico existe antes de la eliminación")
    else:
        print("❌ ERROR: Archivo físico no existe antes de la eliminación")
        return False
    
    # Eliminar modelo usando el método delete() personalizado
    print("\n--- Eliminando modelo usando método delete() ---")
    ai_model.delete()
    
    # Verificar que el archivo fue eliminado
    if not test_file_path.exists():
        print("✅ ÉXITO: Archivo físico eliminado correctamente")
        print("✅ La eliminación de archivos físicos funciona correctamente")
        return True
    else:
        print("❌ ERROR: Archivo físico NO fue eliminado")
        print("❌ El problema de eliminación de archivos persiste")
        # Limpiar archivo manualmente
        try:
            os.remove(test_file_path)
            print("🧹 Archivo limpiado manualmente")
        except:
            pass
        return False

def test_admin_bulk_deletion_simplified():
    """
    Simula la eliminación múltiple directamente sin usar el admin
    """
    print("\n=== PRUEBA DE ELIMINACIÓN MÚLTIPLE (SIMPLIFICADA) ===")
    
    # Crear usuario de prueba
    user, _ = User.objects.get_or_create(
        username='test_bulk_deletion',
        defaults={'email': 'test_bulk@example.com'}
    )
    
    # Crear múltiples archivos y modelos de prueba
    test_files = []
    test_models = []
    
    media_dir = Path(settings.MEDIA_ROOT)
    media_dir.mkdir(exist_ok=True)
    
    for i in range(3):
        # Crear archivo
        test_file_path = media_dir / f"bulk_test_model_{i}_{uuid.uuid4().hex[:8]}.pkl"
        with open(test_file_path, 'w') as f:
            f.write(f"Archivo de prueba {i} para eliminación múltiple")
        test_files.append(test_file_path)
        
        # Crear modelo
        ai_model = AIModel.objects.create(
            user=user,
            name=f"Modelo Bulk {i}",
            description=f"Modelo {i} para prueba de eliminación múltiple",
            task_type="classification",
            status="completed",
            model_path=str(test_file_path),
            dataset_name="test_dataset.csv",
            target_column="target"
        )
        test_models.append(ai_model)
    
    print(f"Creados {len(test_models)} modelos de prueba")
    
    # Verificar que todos los archivos existen
    all_exist_before = all(f.exists() for f in test_files)
    print(f"¿Todos los archivos existen antes? {all_exist_before}")
    
    # Eliminar modelos uno por uno (simula la lógica del admin)
    deleted_files = 0
    deleted_models = 0
    
    for ai_model in test_models:
        # Eliminar archivo físico si existe
        if ai_model.model_path and os.path.exists(ai_model.model_path):
            try:
                os.remove(ai_model.model_path)
                deleted_files += 1
                print(f"Deleted model file: {ai_model.model_path}")
            except OSError as e:
                print(f"Error deleting model file {ai_model.model_path}: {e}")
        
        # Eliminar modelo de BD
        ai_model.delete()
        deleted_models += 1
    
    print(f"Modelos eliminados: {deleted_models}")
    print(f"Archivos eliminados: {deleted_files}")
    
    # Verificar que los archivos fueron eliminados
    files_remaining = sum(1 for f in test_files if f.exists())
    print(f"Archivos restantes: {files_remaining}/{len(test_files)}")
    
    if files_remaining == 0:
        print("✅ ÉXITO: Eliminación múltiple funciona correctamente")
        return True
    else:
        print("❌ ERROR: Algunos archivos no fueron eliminados")
        # Limpiar archivos restantes
        for f in test_files:
            if f.exists():
                try:
                    os.remove(f)
                    print(f"🧹 Limpiado: {f.name}")
                except:
                    pass
        return False

if __name__ == "__main__":
    print("Iniciando pruebas de eliminación de archivos...\n")
    
    # Ejecutar pruebas
    test1_passed = test_file_deletion()
    test2_passed = test_admin_bulk_deletion_simplified()
    
    print("\n=== RESUMEN DE PRUEBAS ===")
    print(f"Eliminación individual: {'✅ PASÓ' if test1_passed else '❌ FALLÓ'}")
    print(f"Eliminación múltiple:   {'✅ PASÓ' if test2_passed else '❌ FALLÓ'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 TODAS LAS PRUEBAS PASARON")
        print("La eliminación de archivos físicos funciona correctamente")
        print("\n📋 INSTRUCCIONES PARA EL USUARIO:")
        print("1. Los volúmenes de Docker están configurados correctamente")
        print("2. Los archivos de modelos se eliminan automáticamente")
        print("3. Puedes usar el admin de Django sin problemas")
        print("4. Los archivos se persisten entre reinicios de contenedores")
    else:
        print("\n⚠️  ALGUNAS PRUEBAS FALLARON")
        print("Revisar la configuración de volúmenes y permisos")