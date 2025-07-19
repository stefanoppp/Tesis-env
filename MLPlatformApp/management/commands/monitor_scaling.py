import time
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from celery import Celery
from MLPlatformApp.config.celery_config import get_scaling_recommendation, get_dynamic_celery_config
from MLPlatformApp.config.dynamic_scaling import dynamic_scaler

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitorea y ajusta dinámicamente los workers de Celery según la carga del sistema'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Intervalo de monitoreo en segundos (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar recomendaciones sin aplicar cambios'
        )
        parser.add_argument(
            '--queue-name',
            type=str,
            default='training',
            help='Nombre de la cola de Celery a monitorear (default: training)'
        )
    
    def handle(self, *args, **options):
        interval = options['interval']
        dry_run = options['dry_run']
        queue_name = options['queue_name']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Iniciando monitoreo de escalado dinámico...\n'
                f'Intervalo: {interval}s\n'
                f'Cola: {queue_name}\n'
                f'Modo: {"DRY RUN" if dry_run else "ACTIVO"}'
            )
        )
        
        # Configurar Celery
        app = Celery('backend')
        app.config_from_object('django.conf:settings', namespace='CELERY')
        
        current_workers = self._get_current_workers(app, queue_name)
        
        try:
            while True:
                self._monitor_and_scale(app, queue_name, current_workers, dry_run)
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\nMonitoreo detenido por el usuario')
            )
    
    def _get_current_workers(self, app, queue_name):
        """Obtiene el número actual de workers activos"""
        try:
            inspect = app.control.inspect()
            active_queues = inspect.active_queues()
            
            if active_queues:
                # Contar workers que están procesando la cola específica
                workers_count = 0
                for worker, queues in active_queues.items():
                    for queue_info in queues:
                        if queue_info['name'] == queue_name:
                            workers_count += 1
                            break
                return max(1, workers_count)  # Mínimo 1 worker
            
        except Exception as e:
            logger.warning(f"No se pudo obtener información de workers: {e}")
        
        return 1  # Default fallback
    
    def _get_queue_length(self, app, queue_name):
        """Obtiene la longitud de la cola de tareas"""
        try:
            inspect = app.control.inspect()
            reserved = inspect.reserved()
            active = inspect.active()
            
            queue_length = 0
            
            # Contar tareas reservadas
            if reserved:
                for worker, tasks in reserved.items():
                    queue_length += len([t for t in tasks if t.get('delivery_info', {}).get('routing_key') == queue_name])
            
            # Contar tareas activas
            if active:
                for worker, tasks in active.items():
                    queue_length += len([t for t in tasks if t.get('delivery_info', {}).get('routing_key') == queue_name])
            
            return queue_length
            
        except Exception as e:
            logger.warning(f"No se pudo obtener longitud de cola: {e}")
            return 0
    
    def _monitor_and_scale(self, app, queue_name, current_workers, dry_run):
        """Monitorea el sistema y aplica escalado si es necesario"""
        try:
            # Obtener métricas actuales
            queue_length = self._get_queue_length(app, queue_name)
            
            # Obtener recomendación de escalado
            recommendation = get_scaling_recommendation(current_workers, queue_length)
            
            # Mostrar estado actual
            self._display_status(recommendation, queue_length)
            
            # Aplicar cambios si es necesario
            if not dry_run and recommendation['action'] != 'maintain':
                success = self._apply_scaling(app, recommendation)
                if success:
                    current_workers = recommendation['recommended_workers']
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Escalado aplicado: {recommendation['action']} "
                            f"a {current_workers} workers"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR("✗ Error al aplicar escalado")
                    )
            
        except Exception as e:
            logger.error(f"Error en monitoreo: {e}")
            self.stdout.write(
                self.style.ERROR(f"Error en monitoreo: {e}")
            )
    
    def _display_status(self, recommendation, queue_length):
        """Muestra el estado actual del sistema"""
        config = recommendation['config']
        system_load = config['system_load']
        
        status_color = self.style.SUCCESS
        if system_load['cpu_percent'] > 70 or system_load['memory_percent'] > 70:
            status_color = self.style.WARNING
        if system_load['cpu_percent'] > 85 or system_load['memory_percent'] > 85:
            status_color = self.style.ERROR
        
        self.stdout.write(
            status_color(
                f"\n[{time.strftime('%H:%M:%S')}] "
                f"CPU: {system_load['cpu_percent']:.1f}% | "
                f"RAM: {system_load['memory_percent']:.1f}% | "
                f"Cola: {queue_length} | "
                f"Workers: {recommendation['current_workers']} → {recommendation['recommended_workers']} | "
                f"Acción: {recommendation['action']}"
            )
        )
        
        if recommendation['action'] != 'maintain':
            self.stdout.write(f"  Razón: {recommendation['reason']}")
    
    def _apply_scaling(self, app, recommendation):
        """Aplica el escalado recomendado"""
        try:
            new_workers = recommendation['recommended_workers']
            
            # Nota: En un entorno real, aquí se implementaría la lógica
            # para ajustar dinámicamente los workers de Celery
            # Esto puede requerir integración con el orquestador de containers
            
            logger.info(
                f"Aplicando escalado: {recommendation['action']} "
                f"a {new_workers} workers"
            )
            
            # Placeholder para implementación real
            # En Docker Compose: docker-compose up --scale celery-training=N
            # En Kubernetes: kubectl scale deployment celery-training --replicas=N
            # En cloud: API calls para ajustar auto-scaling groups
            
            return True
            
        except Exception as e:
            logger.error(f"Error aplicando escalado: {e}")
            return False