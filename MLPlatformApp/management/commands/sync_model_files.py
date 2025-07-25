from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from MLPlatformApp.models import AIModel
import os
import logging

class Command(BaseCommand):
    help = 'Sincroniza la base de datos con los archivos físicos de modelos'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué se haría sin hacer cambios reales'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Sincronizar solo modelos de un usuario específico'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        target_user = options['user']
        
        self.stdout.write(self.style.SUCCESS('=== SINCRONIZACIÓN DE ARCHIVOS DE MODELOS ==='))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: No se harán cambios reales'))
        
        # Filtrar modelos según usuario si se especifica
        if target_user:
            try:
                user = User.objects.get(username=target_user)
                models = AIModel.objects.filter(user=user)
                self.stdout.write(f'Sincronizando modelos del usuario: {target_user}')
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Usuario "{target_user}" no encontrado'))
                return
        else:
            models = AIModel.objects.all()
            self.stdout.write('Sincronizando todos los modelos')
        
        total_models = models.count()
        missing_files = 0
        orphaned_files = 0
        valid_models = 0
        
        self.stdout.write(f'\nTotal de modelos en BD: {total_models}')
        
        # 1. Verificar modelos en BD que no tienen archivo físico
        self.stdout.write('\n1. Verificando modelos sin archivo físico...')
        for model in models:
            if model.model_path and not os.path.exists(model.model_path):
                missing_files += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ ARCHIVO FALTANTE: {model.name} ({model.id}) - {model.model_path}'
                    )
                )
                
                if not dry_run:
                    # Marcar como fallido o eliminar según el estado
                    if model.status == 'completed':
                        model.status = 'failed'
                        model.save()
                        self.stdout.write(
                            self.style.WARNING(
                                f'   → Modelo marcado como "failed" debido a archivo faltante'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'   → Modelo ya estaba en estado "{model.status}"'
                            )
                        )
            elif model.model_path and os.path.exists(model.model_path):
                valid_models += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ VÁLIDO: {model.name} ({str(model.id)[:8]}...) - {model.status}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  SIN RUTA: {model.name} ({str(model.id)[:8]}...) - {model.status}'
                    )
                )
        
        # 2. Verificar archivos huérfanos (archivos sin modelo en BD)
        self.stdout.write('\n2. Verificando archivos huérfanos...')
        media_models_dir = 'media/models'
        
        if os.path.exists(media_models_dir):
            for username in os.listdir(media_models_dir):
                user_dir = os.path.join(media_models_dir, username)
                if os.path.isdir(user_dir):
                    for filename in os.listdir(user_dir):
                        if filename.endswith('.pkl'):
                            file_path = os.path.join(user_dir, filename)
                            
                            # Buscar si existe un modelo con esta ruta
                            model_exists = AIModel.objects.filter(model_path=file_path).exists()
                            
                            if not model_exists:
                                orphaned_files += 1
                                self.stdout.write(
                                    self.style.ERROR(
                                        f'🗑️  ARCHIVO HUÉRFANO: {file_path}'
                                    )
                                )
                                
                                if not dry_run:
                                    try:
                                        os.remove(file_path)
                                        self.stdout.write(
                                            self.style.SUCCESS(
                                                f'   → Archivo huérfano eliminado'
                                            )
                                        )
                                    except OSError as e:
                                        self.stdout.write(
                                            self.style.ERROR(
                                                f'   → Error al eliminar: {e}'
                                            )
                                        )
        
        # 3. Resumen final
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('RESUMEN DE SINCRONIZACIÓN:'))
        self.stdout.write(f'Total de modelos en BD: {total_models}')
        self.stdout.write(f'Modelos válidos: {valid_models}')
        self.stdout.write(f'Archivos faltantes: {missing_files}')
        self.stdout.write(f'Archivos huérfanos: {orphaned_files}')
        
        if dry_run:
            self.stdout.write('\n' + self.style.WARNING('Para aplicar los cambios, ejecuta sin --dry-run'))
        else:
            self.stdout.write('\n' + self.style.SUCCESS('Sincronización completada'))
        
        if missing_files > 0 or orphaned_files > 0:
            self.stdout.write(
                self.style.WARNING(
                    '\nRecomendación: Ejecuta este comando periódicamente para mantener la consistencia'
                )
            )