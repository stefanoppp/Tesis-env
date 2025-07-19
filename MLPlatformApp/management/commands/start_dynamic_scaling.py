import time
import logging
import psutil
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from MLPlatformApp.config.dynamic_scaling import dynamic_scaler
from MLPlatformApp.config.celery_config import get_dynamic_celery_config, get_scaling_recommendation

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Inicia el monitoreo y escalado dinámico de workers de Celery'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Intervalo de monitoreo regular en segundos (default: 30)'
        )
        parser.add_argument(
            '--immediate-check-interval',
            type=int,
            default=5,
            help='Intervalo mínimo entre checks inmediatos en segundos (default: 5)'
        )
        parser.add_argument(
            '--critical-cpu-threshold',
            type=float,
            default=85.0,
            help='Umbral crítico de CPU para trigger inmediato (default: 85.0)'
        )
        parser.add_argument(
            '--critical-memory-threshold',
            type=float,
            default=85.0,
            help='Umbral crítico de memoria para trigger inmediato (default: 85.0)'
        )
        parser.add_argument(
            '--spike-threshold',
            type=float,
            default=20.0,
            help='Umbral de pico de carga para trigger inmediato (default: 20.0)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar recomendaciones sin aplicar cambios'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada'
        )
        parser.add_argument(
            '--cpu-threshold',
            type=float,
            default=80.0,
            help='Umbral de CPU para escalado regular (default: 80.0)'
        )
        parser.add_argument(
            '--memory-threshold',
            type=float,
            default=80.0,
            help='Umbral de memoria para escalado regular (default: 80.0)'
        )
    
    def handle(self, *args, **options):
        interval = options['interval']
        immediate_check_interval = options['immediate_check_interval']
        critical_cpu_threshold = options['critical_cpu_threshold']
        critical_memory_threshold = options['critical_memory_threshold']
        spike_threshold = options['spike_threshold']
        dry_run = options['dry_run']
        verbose = options['verbose']
        cpu_threshold = options['cpu_threshold']
        memory_threshold = options['memory_threshold']
        
        # Inicializar variables para triggers inmediatos
        last_regular_check = 0
        last_immediate_check = 0
        cpu_history = []
        memory_history = []
        max_history_size = 5
        
        self.stdout.write(
            self.style.SUCCESS(
                f'🚀 Iniciando monitoreo de escalado dinámico con TRIGGERS INMEDIATOS...\n'
                f'📊 Monitoreo regular: cada {interval}s\n'
                f'⚡ Triggers inmediatos: cada {immediate_check_interval}s (mínimo)\n'
                f'🔥 Umbrales regulares: CPU {cpu_threshold}%, RAM {memory_threshold}%\n'
                f'🚨 Umbrales críticos: CPU {critical_cpu_threshold}%, RAM {critical_memory_threshold}%\n'
                f'📈 Umbral picos: {spike_threshold}%\n'
                f'🧪 Modo: {"DRY-RUN" if dry_run else "ACTIVO"}\n'
            )
        )
        
        # Configurar límites
        os.environ['CPU_THRESHOLD'] = str(cpu_threshold)
        os.environ['MEMORY_THRESHOLD'] = str(memory_threshold)
        
        try:
            while True:
                current_time = time.time()
                
                # 1. MONITOREO REGULAR (cada 30 segundos)
                regular_check_needed = current_time - last_regular_check >= interval
                
                # 2. TRIGGER INMEDIATO (verificar condiciones críticas)
                immediate_check_needed, cpu_history, memory_history = self._should_trigger_immediate_check(
                    current_time, last_immediate_check, immediate_check_interval,
                    critical_cpu_threshold, critical_memory_threshold, spike_threshold,
                    cpu_history, memory_history, max_history_size
                )
                
                if regular_check_needed or immediate_check_needed:
                    check_type = "REGULAR" if regular_check_needed else "INMEDIATO"
                    
                    self._monitor_and_scale(
                        dry_run=dry_run,
                        verbose=verbose,
                        cpu_threshold=cpu_threshold,
                        memory_threshold=memory_threshold,
                        trigger_type=check_type,
                        critical_thresholds={
                            'cpu': critical_cpu_threshold,
                            'memory': critical_memory_threshold
                        }
                    )
                    
                    if regular_check_needed:
                        last_regular_check = current_time
                    if immediate_check_needed:
                        last_immediate_check = current_time
                
                # Dormir un poco para no saturar el CPU
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\n⏹️  Deteniendo monitoreo de escalado dinámico')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error en monitoreo: {e}')
            )
            logger.error(f"Error en monitoreo de escalado: {e}", exc_info=True)
    
    def _should_trigger_immediate_check(self, current_time, last_immediate_check, immediate_check_interval,
                                       critical_cpu_threshold, critical_memory_threshold, spike_threshold,
                                       cpu_history, memory_history, max_history_size):
        """Determinar si se debe hacer un check inmediato"""
        # Evitar spam de checks inmediatos
        if current_time - last_immediate_check < immediate_check_interval:
            return False, cpu_history, memory_history
        
        try:
            # Obtener métricas rápidas
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            
            # Actualizar historial primero
            cpu_history.append(cpu_percent)
            memory_history.append(memory_percent)
            
            # Mantener solo las últimas N mediciones
            if len(cpu_history) > max_history_size:
                cpu_history.pop(0)
            if len(memory_history) > max_history_size:
                memory_history.pop(0)
            
            # TRIGGER 1: Condiciones críticas (CPU/RAM > 85%)
            if cpu_percent > critical_cpu_threshold or memory_percent > critical_memory_threshold:
                self.stdout.write(
                    self.style.ERROR(
                        f"🚨 TRIGGER CRÍTICO: CPU {cpu_percent:.1f}%, RAM {memory_percent:.1f}% "
                        f"(límites críticos: CPU>{critical_cpu_threshold}%, RAM>{critical_memory_threshold}%)"
                    )
                )
                return True, cpu_history, memory_history
            
            # TRIGGER 2: Picos súbitos de carga
            if len(cpu_history) >= 2:
                # Calcular promedio de valores anteriores (sin incluir el actual)
                prev_cpu_values = cpu_history[:-1]  # Todos menos el último (actual)
                prev_memory_values = memory_history[:-1]
                
                if prev_cpu_values and prev_memory_values:
                    avg_cpu = sum(prev_cpu_values) / len(prev_cpu_values)
                    avg_memory = sum(prev_memory_values) / len(prev_memory_values)
                    
                    cpu_spike = cpu_percent - avg_cpu > spike_threshold
                    memory_spike = memory_percent - avg_memory > spike_threshold
                else:
                    cpu_spike = False
                    memory_spike = False
                
                if cpu_spike or memory_spike:
                    self.stdout.write(
                        self.style.WARNING(
                            f"📈 TRIGGER PICO DE CARGA: CPU {cpu_percent:.1f}% (+{cpu_percent-avg_cpu:.1f}), "
                            f"RAM {memory_percent:.1f}% (+{memory_percent-avg_memory:.1f})"
                        )
                    )
                    return True, cpu_history, memory_history
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error en trigger inmediato: {e}")
            )
        
        return False, cpu_history, memory_history
    
    def _monitor_and_scale(self, dry_run, verbose, cpu_threshold, memory_threshold, 
                          trigger_type="REGULAR", critical_thresholds=None):
        """Monitorear sistema y aplicar escalado si es necesario"""
        try:
            # Obtener métricas del sistema
            interval = 0.5 if trigger_type == "INMEDIATO" else 1
            cpu_percent = psutil.cpu_percent(interval=interval)
            memory = psutil.virtual_memory()
            
            # Simular longitud de cola (en un caso real, obtener de Redis/Celery)
            queue_length = self._get_queue_length()
            
            # Obtener workers actuales
            current_workers = getattr(settings, 'CELERY_WORKER_CONCURRENCY', 2)
            
            # Obtener recomendación de escalado
            recommendation = get_scaling_recommendation(
                current_workers=current_workers,
                queue_length=queue_length
            )
            
            # Determinar estado del sistema
            system_status = self._get_system_status(
                cpu_percent, memory.percent, cpu_threshold, memory_threshold
            )
            
            # Para triggers inmediatos, usar umbrales críticos si están disponibles
            if trigger_type == "INMEDIATO" and critical_thresholds:
                if cpu_percent > critical_thresholds['cpu'] or memory.percent > critical_thresholds['memory']:
                    system_status = 'critical'
            
            # Mostrar información con indicador de tipo de trigger
            urgency_icon = "🚨" if trigger_type == "INMEDIATO" else "📊"
            if verbose or system_status != 'normal' or recommendation['action'] != 'maintain' or trigger_type == "INMEDIATO":
                self.stdout.write(
                    f'{urgency_icon} MONITOREO {trigger_type}: CPU {cpu_percent:.1f}%, RAM {memory.percent:.1f}%, '
                    f'Cola: {queue_length} tareas'
                )
                
                self._display_status(
                    cpu_percent, memory.percent, queue_length, 
                    current_workers, recommendation, system_status
                )
            
            # Aplicar escalado si no es dry-run
            if not dry_run and recommendation['action'] != 'maintain':
                urgency = "🚨 CRÍTICO" if trigger_type == "INMEDIATO" else "⚠️ REGULAR"
                self.stdout.write(
                    self.style.ERROR(
                        f'{urgency} ESCALANDO ({trigger_type}): {recommendation["action"]} - {recommendation["reason"]}'
                    )
                )
                self._apply_scaling(recommendation)
            
        except Exception as e:
            logger.error(f"Error en _monitor_and_scale ({trigger_type}): {e}", exc_info=True)
    
    def _get_queue_length(self):
        """Obtener longitud de cola de Celery (simulado por ahora)"""
        # En un caso real, esto se obtendría de Redis/Celery
        # Por ahora, simular basado en carga del sistema
        cpu_percent = psutil.cpu_percent()
        if cpu_percent > 70:
            return min(10, int(cpu_percent / 10))  # Simular cola creciente
        return 0
    
    def _get_system_status(self, cpu_percent, memory_percent, cpu_threshold, memory_threshold):
        """Determinar estado del sistema"""
        if cpu_percent > cpu_threshold or memory_percent > memory_threshold:
            return 'overloaded'
        elif cpu_percent > cpu_threshold * 0.8 or memory_percent > memory_threshold * 0.8:
            return 'high_load'
        elif cpu_percent < 30 and memory_percent < 30:
            return 'low_load'
        return 'normal'
    
    def _display_status(self, cpu_percent, memory_percent, queue_length, 
                       current_workers, recommendation, system_status):
        """Mostrar estado actual del sistema"""
        # Colores según estado
        status_colors = {
            'normal': self.style.SUCCESS,
            'low_load': self.style.HTTP_INFO,
            'high_load': self.style.WARNING,
            'overloaded': self.style.ERROR
        }
        
        action_colors = {
            'maintain': self.style.SUCCESS,
            'scale_up': self.style.HTTP_INFO,
            'scale_down': self.style.WARNING
        }
        
        status_color = status_colors.get(system_status, self.style.SUCCESS)
        action_color = action_colors.get(recommendation['action'], self.style.SUCCESS)
        
        action_text = recommendation['action'].upper()
        self.stdout.write(
            f"\n📊 {status_color(f'Sistema: {system_status.upper()}')} | "
            f"CPU: {cpu_percent:.1f}% | RAM: {memory_percent:.1f}% | "
            f"Cola: {queue_length} | Workers: {current_workers}\n"
            f"🎯 {action_color(f'Acción: {action_text}')} - {recommendation['reason']}"
        )
        
        if recommendation['action'] != 'maintain':
            self.stdout.write(
                f"   Configuración recomendada: {recommendation['recommended_config']}"
            )
    
    def _apply_scaling(self, recommendation):
        """Aplicar escalado (placeholder para implementación real)"""
        try:
            self.stdout.write(
                self.style.HTTP_INFO(
                    f"🔧 Aplicando escalado: {recommendation['action']} - {recommendation['reason']}"
                )
            )
            
            # Aquí se implementaría la lógica real de escalado
            # Por ejemplo:
            # - Ajustar configuración de Celery dinámicamente
            # - Enviar señales a Docker Compose
            # - Actualizar configuración en Kubernetes
            # - Modificar variables de entorno
            
            logger.info(
                f"Escalado aplicado: {recommendation['action']} - {recommendation['reason']}"
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error aplicando escalado: {e}")
            )
            logger.error(f"Error aplicando escalado: {e}", exc_info=True)