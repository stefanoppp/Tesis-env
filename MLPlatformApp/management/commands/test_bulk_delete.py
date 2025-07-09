from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from MLPlatformApp.models import AIModel
import tempfile
import os

class Command(BaseCommand):
    help = 'Prueba la eliminación múltiple de modelos con archivos físicos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Limpiar archivos y modelos de prueba creados anteriormente',
        )

    def handle(self, *args, **options):
        if options['cleanup']:
            self.cleanup_test_data()
        else:
            self.run_bulk_delete_test()

    def cleanup_test_data(self):
        """Limpiar datos de prueba"""
        self.stdout.write("🧹 Limpiando datos de prueba...")
        
        # Eliminar usuario y modelos de prueba
        try:
            user = User.objects.get(username='test_bulk_delete')
            models_count = AIModel.objects.filter(user=user).count()
            user.delete()  # Esto eliminará en cascada los modelos
            self.stdout.write(
                self.style.SUCCESS(f'✅ Eliminado usuario de prueba y {models_count} modelos')
            )
        except User.DoesNotExist:
            self.stdout.write("ℹ️ No hay datos de prueba para limpiar")

    def run_bulk_delete_test(self):
        """Ejecutar prueba de eliminación múltiple"""
        self.stdout.write("🧪 Iniciando prueba de eliminación múltiple...")
        
        # 1. Crear usuario de prueba
        user, created = User.objects.get_or_create(
            username='test_bulk_delete',
            defaults={'email': 'test@example.com'}
        )
        
        if not created:
            self.stdout.write("ℹ️ Usuario de prueba ya existe, eliminando modelos previos...")
            AIModel.objects.filter(user=user).delete()
        
        # 2. Crear directorio temporal
        test_dir = tempfile.mkdtemp(prefix='modelium_bulk_test_')
        self.stdout.write(f"📁 Directorio temporal: {test_dir}")
        
        # 3. Crear modelos con archivos físicos
        models_created = []
        files_created = []
        
        for i in range(3):
            # Crear archivo físico
            file_path = os.path.join(test_dir, f'test_model_{i}.pkl')
            with open(file_path, 'w') as f:
                f.write(f'Contenido de prueba para modelo {i}')
            files_created.append(file_path)
            
            # Crear modelo en BD
            model = AIModel.objects.create(
                user=user,
                name=f'Test Model {i}',
                description=f'Modelo de prueba para bulk delete {i}',
                task_type='classification',
                target_column='target',
                dataset_name=f'test_dataset_{i}.csv',
                model_path=file_path,
                status='completed'
            )
            models_created.append(model)
            
        self.stdout.write(f"✅ Creados {len(models_created)} modelos con archivos físicos")
        
        # 4. Verificar archivos antes de eliminación
        files_before = sum(1 for f in files_created if os.path.exists(f))
        self.stdout.write(f"📋 Archivos existentes antes de eliminación: {files_before}/{len(files_created)}")
        
        # 5. Simular eliminación múltiple usando la vista
        from MLPlatformApp.views import DeleteMultipleModelsView
        
        view = DeleteMultipleModelsView()
        model_ids = [str(model.id) for model in models_created]
        models_to_delete = AIModel.objects.filter(id__in=model_ids, user=user)
        
        self.stdout.write(f"🗑️ Eliminando {models_to_delete.count()} modelos...")
        
        # Eliminar archivos físicos
        files_cleanup_result = view._delete_model_files(models_to_delete)
        
        # Eliminar de BD
        deleted_count = models_to_delete.count()
        models_to_delete.delete()
        
        # 6. Verificar resultados
        files_after = sum(1 for f in files_created if os.path.exists(f))
        
        self.stdout.write("\n📊 RESULTADOS:")
        self.stdout.write(f"   Modelos eliminados de BD: {deleted_count}")
        self.stdout.write(f"   Archivos antes: {files_before}")
        self.stdout.write(f"   Archivos después: {files_after}")
        self.stdout.write(f"   Archivos eliminados exitosamente: {files_cleanup_result['files_deleted']}")
        self.stdout.write(f"   Archivos con error: {files_cleanup_result['files_failed']}")
        
        # 7. Evaluar éxito
        success = (
            files_before == len(files_created) and
            files_after == 0 and
            files_cleanup_result['files_failed'] == 0 and
            deleted_count == len(models_created)
        )
        
        if success:
            self.stdout.write(
                self.style.SUCCESS('🎉 ¡PRUEBA EXITOSA! Todos los archivos y modelos fueron eliminados correctamente')
            )
        else:
            self.stdout.write(
                self.style.ERROR('❌ PRUEBA FALLIDA: Algunos archivos o modelos no fueron eliminados')
            )
            
            if files_cleanup_result['files_failed'] > 0:
                self.stdout.write("Errores en archivos:")
                for failed_file in files_cleanup_result['failed_files']:
                    self.stdout.write(f"  - {failed_file['path']}: {failed_file['error']}")
        
        # 8. Instrucciones de limpieza
        self.stdout.write(f"\n🧹 Para limpiar los datos de prueba ejecuta:")
        self.stdout.write(f"   python manage.py test_bulk_delete --cleanup")
        
        return success
