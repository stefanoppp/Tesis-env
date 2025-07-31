from django.core.management.base import BaseCommand
from MLPlatformApp.config.hardware_optimization import hardware_optimizer
from MLPlatformApp.config.celery_config import log_celery_recommendations
import logging

class Command(BaseCommand):
    help = 'Muestra la configuración optimizada de hardware y Celery para el sistema actual'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Muestra comandos para aplicar la configuración recomendada',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Muestra información detallada del sistema',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== CONFIGURACIÓN OPTIMIZADA DE HARDWARE ===' + '\n'))
        
        # Configurar logging para capturar la salida del optimizador
        if options['verbose']:
            logging.basicConfig(level=logging.INFO)
        
        # Obtener configuración optimizada
        config = hardware_optimizer.get_optimal_config()
        
        # Obtener información del sistema
        system_info = hardware_optimizer.get_system_info()
        
        # Mostrar información del sistema
        self.stdout.write(self.style.HTTP_INFO('📊 INFORMACIÓN DEL SISTEMA:'))
        if 'cpu_info' in system_info and system_info['cpu_info']:
            cpu_info = system_info['cpu_info']
            self.stdout.write(f"  • Procesador: {cpu_info.get('brand', 'Desconocido')}")
            self.stdout.write(f"  • Arquitectura: {cpu_info.get('architecture', 'Desconocida')}")
        self.stdout.write(f"  • CPU Cores (Físicos): {system_info['cpu_count_physical']}")
        self.stdout.write(f"  • CPU Cores (Lógicos): {system_info['cpu_count_logical']}")
        self.stdout.write(f"  • RAM Total: {system_info['memory_total_gb']:.1f} GB")
        self.stdout.write(f"  • RAM Disponible: {system_info['memory_available_gb']:.1f} GB")
        self.stdout.write(f"  • GPU disponible: {'✅ Sí' if system_info['gpu_available'] else '❌ No'}")
        self.stdout.write('')
        
        # Mostrar configuración recomendada
        self.stdout.write(self.style.HTTP_INFO('⚙️ CONFIGURACIÓN RECOMENDADA:'))
        self.stdout.write(f"  • Concurrencia Celery: {config['recommended_concurrency']}")
        self.stdout.write(f"  • Jobs PyCaret (n_jobs): {config['n_jobs']}")
        self.stdout.write(f"  • Pliegues CV: {config['cv_folds']}")
        self.stdout.write(f"  • Tiempo límite por modelo: {config['budget_time']} min (durante comparación)")
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('📊 MODELOS SELECCIONADOS:'))
        if 'preferred_models' in config:
            models = config['preferred_models']
            self.stdout.write(f"  • Modelos preferidos ({len(models)}): {', '.join(models[:5])}{'...' if len(models) > 5 else ''}")
        else:
            # Fallback para compatibilidad
            self.stdout.write("  • Modelos: Configuración estándar")
        self.stdout.write('')
        
        # Mostrar recomendaciones de Celery
        self.stdout.write(self.style.HTTP_INFO('🔧 CONFIGURACIÓN DE CELERY:'))
        log_celery_recommendations()
        
        if options['apply']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('📋 COMANDOS PARA APLICAR:'))
            self.stdout.write('')
            
            # Comando para Celery
            self.stdout.write(self.style.HTTP_INFO('1. Reiniciar Celery con configuración optimizada:'))
            celery_cmd = f"celery -A backend worker --loglevel=info --concurrency={config['recommended_concurrency']} -Q training"
            self.stdout.write(f"   {celery_cmd}")
            self.stdout.write('')
            
            # Docker Compose
            self.stdout.write(self.style.HTTP_INFO('2. Actualizar docker-compose.yml:'))
            self.stdout.write("   Cambiar la línea de comando del servicio celery-training a:")
            self.stdout.write(f"   command: {celery_cmd}")
            self.stdout.write('')
            
            # Instalación de dependencias GPU
            if config['use_gpu']:
                self.stdout.write(self.style.SUCCESS('3. GPU detectada - Instalar dependencias opcionales:'))
                self.stdout.write("   Para NVIDIA: pip install cuml cudf-cu11 cupy-cuda11x")
                self.stdout.write("   Para AMD: pip uninstall torch && pip install torch-rocm")
            else:
                self.stdout.write(self.style.HTTP_INFO('3. Optimizaciones CPU - Instalar dependencias opcionales:'))
                self.stdout.write("   pip install scikit-learn-intelex numba")
            self.stdout.write('')
        
        # Mostrar advertencias
        self.stdout.write(self.style.WARNING('⚠️ CONSIDERACIONES IMPORTANTES:'))
        
        if config['use_gpu']:
            self.stdout.write("  • GPU detectada: Se usará aceleración por GPU cuando sea posible")
            self.stdout.write("  • Concurrencia reducida para evitar conflictos de GPU")
            self.stdout.write("  • Para NVIDIA: Asegúrate de tener CUDA instalado correctamente")
            self.stdout.write("  • Para AMD: Asegúrate de tener ROCm instalado correctamente")
        else:
            self.stdout.write("  • Sin GPU: Configuración optimizada para CPU")
            self.stdout.write("  • Considera instalar dependencias de optimización CPU")
        
        if config['recommended_concurrency'] < 2:
            self.stdout.write("  • ⚠️ Sistema con recursos limitados detectado")
            self.stdout.write("  • Se recomienda monitorear el uso de CPU y memoria")
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ Configuración completada. Usa --apply para ver comandos específicos.'))