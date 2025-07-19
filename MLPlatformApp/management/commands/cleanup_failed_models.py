from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from MLPlatformApp.models import AIModel
import os
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Limpia modelos fallidos antiguos para liberar espacio y recursos'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='Días de antigüedad para considerar modelos fallidos como eliminables'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se eliminaría sin hacer cambios reales'
        )
    
    def handle(self, *args, **options):
        # Obtener configuración
        ml_settings = getattr(settings, 'ML_PLATFORM_SETTINGS', {})
        days_threshold = options['days'] or ml_settings.get('CLEANUP_FAILED_MODELS_DAYS', 7)
        dry_run = options['dry_run']
        
        # Calcular fecha límite
        cutoff_date = timezone.now() - timedelta(days=days_threshold)
        
        # Buscar modelos fallidos antiguos
        failed_models = AIModel.objects.filter(
            status='failed',
            created_at__lt=cutoff_date
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Buscando modelos fallidos anteriores a {cutoff_date.strftime("%Y-%m-%d %H:%M:%S")}'
            )
        )
        
        if not failed_models.exists():
            self.stdout.write(
                self.style.SUCCESS('No se encontraron modelos fallidos para limpiar.')
            )
            return
        
        total_models = failed_models.count()
        self.stdout.write(
            self.style.WARNING(f'Encontrados {total_models} modelos fallidos para eliminar')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS('=== MODO DRY-RUN: No se realizarán cambios reales ===')
            )
            for model in failed_models[:10]:  # Mostrar solo los primeros 10
                self.stdout.write(f'  - {model.name} (ID: {model.id}) - Creado: {model.created_at}')
            if total_models > 10:
                self.stdout.write(f'  ... y {total_models - 10} más')
            return
        
        # Eliminar archivos de modelo y registros
        deleted_files = 0
        deleted_models = 0
        
        for model in failed_models:
            try:
                # Eliminar archivo del modelo si existe
                if model.model_path and os.path.exists(model.model_path):
                    os.remove(model.model_path)
                    deleted_files += 1
                    logger.info(f'Archivo eliminado: {model.model_path}')
                
                # Eliminar registro de la base de datos
                model_name = model.name
                model.delete()
                deleted_models += 1
                logger.info(f'Modelo eliminado: {model_name}')
                
            except Exception as e:
                logger.error(f'Error eliminando modelo {model.id}: {str(e)}')
                self.stdout.write(
                    self.style.ERROR(f'Error eliminando modelo {model.name}: {str(e)}')
                )
        
        # Resumen
        self.stdout.write(
            self.style.SUCCESS(
                f'Limpieza completada:\n'
                f'  - Modelos eliminados: {deleted_models}\n'
                f'  - Archivos eliminados: {deleted_files}'
            )
        )
        
        # Estadísticas finales
        remaining_failed = AIModel.objects.filter(status='failed').count()
        total_pending = AIModel.objects.filter(status='pending').count()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Estado actual del sistema:\n'
                f'  - Modelos fallidos restantes: {remaining_failed}\n'
                f'  - Modelos en cola: {total_pending}'
            )
        )