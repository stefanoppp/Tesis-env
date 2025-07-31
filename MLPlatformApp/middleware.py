import logging
import time
import psutil
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from .config.hardware_optimization import hardware_optimizer

logger = logging.getLogger(__name__)

class SystemLoadMiddleware(MiddlewareMixin):
    """
    Middleware para monitorear la carga del sistema y aplicar escalado dinámico.
    Se ejecuta en cada request para mantener el sistema optimizado.
    
    TRIGGERS DE ESCALADO:
    1. Monitoreo regular cada 30 segundos
    2. Trigger inmediato si CPU/RAM > 85% (crítico)
    3. Trigger inmediato si hay picos de carga súbitos
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.last_check = 0
        self.last_immediate_check = 0
        self.check_interval = 30  # Verificar cada 30 segundos
        self.immediate_check_cooldown = 5  # Cooldown para checks inmediatos
        self.dynamic_scaling_enabled = getattr(settings, 'DYNAMIC_SCALING_ENABLED', True)
        
        # Umbrales para triggers inmediatos
        self.critical_cpu_threshold = 85  # Trigger inmediato si CPU > 85%
        self.critical_memory_threshold = 85  # Trigger inmediato si RAM > 85%
        self.load_spike_threshold = 20  # Trigger si carga aumenta >20% súbitamente
        
        # Historial para detectar picos
        self.cpu_history = []
        self.memory_history = []
        self.max_history_size = 5
        
        super().__init__(get_response)
    
    def process_request(self, request):
        """Monitorear sistema antes de procesar request"""
        if not self.dynamic_scaling_enabled:
            return None
            
        current_time = time.time()
        
        # 1. MONITOREO REGULAR (cada 30 segundos)
        regular_check_needed = current_time - self.last_check > self.check_interval
        
        # 2. TRIGGER INMEDIATO (verificar condiciones críticas)
        immediate_check_needed = self._should_trigger_immediate_check(current_time)
        
        if regular_check_needed or immediate_check_needed:
            check_type = "REGULAR" if regular_check_needed else "INMEDIATO"
            self._check_system_load(trigger_type=check_type)
            
            if regular_check_needed:
                self.last_check = current_time
            if immediate_check_needed:
                self.last_immediate_check = current_time
        
        return None
    
    def _should_trigger_immediate_check(self, current_time):
        """Determinar si se debe hacer un check inmediato"""
        # Evitar spam de checks inmediatos
        if current_time - self.last_immediate_check < self.immediate_check_cooldown:
            return False
        
        try:
            # Obtener métricas rápidas (sin interval para ser más rápido)
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            
            # TRIGGER 1: Condiciones críticas (CPU/RAM > 85%)
            if cpu_percent > self.critical_cpu_threshold or memory_percent > self.critical_memory_threshold:
                logger.warning(
                    f"🚨 TRIGGER CRÍTICO: CPU {cpu_percent:.1f}%, RAM {memory_percent:.1f}% "
                    f"(límites críticos: CPU>{self.critical_cpu_threshold}%, RAM>{self.critical_memory_threshold}%)"
                )
                return True
            
            # TRIGGER 2: Picos súbitos de carga
            if self._detect_load_spike(cpu_percent, memory_percent):
                logger.warning(
                    f"📈 TRIGGER PICO DE CARGA: CPU {cpu_percent:.1f}%, RAM {memory_percent:.1f}%"
                )
                return True
            
            # Actualizar historial
            self._update_load_history(cpu_percent, memory_percent)
            
        except Exception as e:
            logger.error(f"Error en trigger inmediato: {e}")
        
        return False
    
    def _detect_load_spike(self, current_cpu, current_memory):
        """Detectar picos súbitos de carga"""
        if len(self.cpu_history) < 2:
            return False
        
        # Calcular promedio de las últimas mediciones
        avg_cpu = sum(self.cpu_history[-3:]) / min(len(self.cpu_history), 3)
        avg_memory = sum(self.memory_history[-3:]) / min(len(self.memory_history), 3)
        
        # Detectar picos (aumento súbito > 20%)
        cpu_spike = current_cpu - avg_cpu > self.load_spike_threshold
        memory_spike = current_memory - avg_memory > self.load_spike_threshold
        
        return cpu_spike or memory_spike
    
    def _update_load_history(self, cpu_percent, memory_percent):
        """Actualizar historial de carga"""
        self.cpu_history.append(cpu_percent)
        self.memory_history.append(memory_percent)
        
        # Mantener solo las últimas N mediciones
        if len(self.cpu_history) > self.max_history_size:
            self.cpu_history.pop(0)
        if len(self.memory_history) > self.max_history_size:
            self.memory_history.pop(0)
    
    def _check_system_load(self, trigger_type="REGULAR"):
        """Verificar carga del sistema y aplicar escalado si es necesario"""
        if not self.dynamic_scaling_enabled:
            return
        
        try:
            # Obtener métricas del sistema
            # Para triggers inmediatos, usar medición más rápida
            interval = 0.5 if trigger_type == "INMEDIATO" else 1
            cpu_percent = psutil.cpu_percent(interval=interval)
            memory = psutil.virtual_memory()
            
            # Límites de seguridad
            cpu_threshold = getattr(settings, 'CPU_THRESHOLD', 80)
            memory_threshold = getattr(settings, 'MEMORY_THRESHOLD', 80)
            
            # Log del tipo de monitoreo
            logger.info(
                f"🔍 MONITOREO {trigger_type}: CPU {cpu_percent:.1f}%, RAM {memory.percent:.1f}% "
                f"(umbrales: CPU<{cpu_threshold}%, RAM<{memory_threshold}%)"
            )
            
            # Verificar si el sistema está sobrecargado
            if cpu_percent > cpu_threshold or memory.percent > memory_threshold:
                logger.warning(
                    f"⚠️ Sistema sobrecargado ({trigger_type}) - CPU: {cpu_percent:.1f}%, RAM {memory.percent:.1f}% "
                    f"(límites: CPU<{cpu_threshold}%, RAM<{memory_threshold}%)"
                )
                
                # Aquí se podría implementar lógica para reducir workers
                # o notificar al sistema de escalado
                self._handle_system_overload(cpu_percent, memory.percent, trigger_type)
            else:
                # Sistema en condiciones normales
                if trigger_type == "INMEDIATO":
                    logger.info(f"✅ Trigger inmediato resuelto - Sistema estable")
            
            if cpu_percent < 50 and memory.percent < 50:
                # Sistema con baja carga, podría escalar hacia arriba si hay demanda
                logger.debug(
                    f"Sistema con baja carga: CPU {cpu_percent:.1f}%, RAM {memory.percent:.1f}%"
                )
        
        except Exception as e:
            logger.error(f"Error monitoreando carga del sistema ({trigger_type}): {e}")
    
    def _handle_system_overload(self, cpu_percent, memory_percent, trigger_type="REGULAR"):
        """Manejar sobrecarga del sistema"""
        try:
            # Obtener información del hardware para logging
            hardware_info = hardware_optimizer.get_system_info()
            
            urgency = "🚨 CRÍTICO" if trigger_type == "INMEDIATO" else "⚠️ REGULAR"
            logger.warning(
                f"{urgency} - Sistema sobrecargado ({trigger_type}): "
                f"CPU {cpu_percent:.1f}%, RAM {memory_percent:.1f}% - "
                f"Hardware: {hardware_info.get('cpu_count', 'N/A')} CPUs, "
                f"{hardware_info.get('total_memory_gb', 'N/A')}GB RAM"
            )
            
            # El autoescalado de Celery se encargará de ajustar los workers
            # basándose en la configuración de hardware_optimizer
                
        except Exception as e:
            logger.error(f"Error manejando sobrecarga del sistema ({trigger_type}): {e}")