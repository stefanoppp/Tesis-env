import psutil
import time
import logging
from typing import Dict, Any, Tuple
from .hardware_optimization import hardware_optimizer

logger = logging.getLogger(__name__)

class DynamicScalingPolicy:
    """
    Política de escalado dinámico para workers de Celery basada en:
    - Hardware disponible (GPU, CPU, RAM)
    - Carga actual del sistema (CPU, memoria)
    - Cantidad de peticiones en cola
    - Límite del 80% de capacidad de cómputo y memoria
    """
    
    def __init__(self):
        self.hardware_config = hardware_optimizer.get_optimal_config()
        self.cpu_threshold = 80.0  # 80% CPU máximo
        self.memory_threshold = 80.0  # 80% memoria máxima
        self.min_workers = 1
        self.monitoring_interval = 30  # segundos
        
    def get_current_system_load(self) -> Dict[str, float]:
        """Obtiene la carga actual del sistema"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_gb': memory.available / (1024**3)
        }
    
    def calculate_optimal_workers(self, queue_length: int = 0) -> Tuple[int, Dict[str, Any]]:
        """
        Calcula el número óptimo de workers basado en:
        - Hardware disponible
        - Carga actual del sistema
        - Longitud de la cola de tareas
        
        Returns:
            Tuple[int, Dict]: (número_workers, configuración_detallada)
        """
        system_load = self.get_current_system_load()
        
        # Configuración base según hardware
        if self.hardware_config['use_gpu']:
            base_config = self._get_gpu_config(system_load, queue_length)
        else:
            base_config = self._get_cpu_only_config(system_load, queue_length)
        
        # Aplicar límites de seguridad
        final_workers = self._apply_safety_limits(base_config['workers'], system_load)
        safety_applied = (final_workers != base_config['workers'] or 
                         system_load['cpu_percent'] >= 80 or 
                         system_load['memory_percent'] >= 75)
        
        config = {
            **base_config,
            'final_workers': final_workers,
            'system_load': system_load,
            'safety_applied': safety_applied
        }
        
        return final_workers, config
    
    def _get_gpu_config(self, system_load: Dict[str, float], queue_length: int) -> Dict[str, Any]:
        """Configuración para sistemas con GPU"""
        # Con GPU: Priorizar GPU + CPU moderado
        base_workers = 2  # Base conservadora
        max_workers = min(6, self.hardware_config['physical_cpu_count'])  # Máximo 6 o cores físicos
        
        # Escalado basado en cola de tareas
        if queue_length > 10:
            workers = min(max_workers, base_workers + (queue_length // 5))
        elif queue_length > 5:
            workers = min(max_workers, base_workers + 1)
        else:
            workers = base_workers
        
        # Reducir si el sistema está sobrecargado
        if system_load['cpu_percent'] > 70 or system_load['memory_percent'] > 70:
            workers = max(self.min_workers, workers - 1)
        
        return {
            'workers': workers,
            'max_workers': max_workers,
            'n_jobs': min(3, self.hardware_config['physical_cpu_count'] // 2),
            'strategy': 'GPU + CPU moderado',
            'queue_factor': queue_length
        }
    
    def _get_cpu_only_config(self, system_load: Dict[str, float], queue_length: int) -> Dict[str, Any]:
        """Configuración para sistemas solo CPU"""
        # Sin GPU: Configuración más conservadora
        if self.hardware_config['memory_gb'] >= 16:
            # Sistema potente
            base_workers = 3
            max_workers = min(5, self.hardware_config['physical_cpu_count'])
            n_jobs = min(4, self.hardware_config['physical_cpu_count'] // 2)
        elif self.hardware_config['memory_gb'] >= 8:
            # Sistema medio
            base_workers = 2
            max_workers = min(4, self.hardware_config['physical_cpu_count'])
            n_jobs = min(2, self.hardware_config['physical_cpu_count'] // 3)
        else:
            # Sistema básico
            base_workers = 1
            max_workers = 2
            n_jobs = 1
        
        # Escalado más conservador sin GPU
        if queue_length > 15:
            workers = min(max_workers, base_workers + (queue_length // 8))
        elif queue_length > 8:
            workers = min(max_workers, base_workers + 1)
        else:
            workers = base_workers
        
        # Reducir agresivamente si hay sobrecarga
        if system_load['cpu_percent'] > 60 or system_load['memory_percent'] > 70:
            workers = max(self.min_workers, workers - 1)
        
        return {
            'workers': workers,
            'max_workers': max_workers,
            'n_jobs': n_jobs,
            'strategy': 'CPU conservador',
            'queue_factor': queue_length
        }
    
    def _apply_safety_limits(self, proposed_workers: int, system_load: Dict[str, float]) -> int:
        """Aplica límites de seguridad para no exceder 80% de capacidad"""
        # Si el sistema ya está al límite, reducir workers agresivamente
        if (system_load['cpu_percent'] >= self.cpu_threshold or 
            system_load['memory_percent'] >= self.memory_threshold):
            return max(self.min_workers, min(proposed_workers - 1, 2))
        
        # Si el sistema está cerca del límite, ser conservador
        if (system_load['cpu_percent'] >= 70 or 
            system_load['memory_percent'] >= 70):
            return min(proposed_workers, max(self.min_workers, self.hardware_config['recommended_concurrency'] // 2))
        
        return proposed_workers
    
    def get_scaling_recommendation(self, current_workers: int, queue_length: int = 0) -> Dict[str, Any]:
        """Obtiene recomendación de escalado completa"""
        optimal_workers, config = self.calculate_optimal_workers(queue_length)
        
        recommendation = {
            'current_workers': current_workers,
            'recommended_workers': optimal_workers,
            'action': 'maintain',
            'reason': 'Sistema estable',
            'config': config
        }
        
        if optimal_workers > current_workers:
            recommendation.update({
                'action': 'scale_up',
                'reason': f'Cola: {queue_length}, Carga: {config["system_load"]["cpu_percent"]:.1f}% CPU'
            })
        elif optimal_workers < current_workers:
            recommendation.update({
                'action': 'scale_down',
                'reason': f'Sobrecarga: {config["system_load"]["cpu_percent"]:.1f}% CPU, {config["system_load"]["memory_percent"]:.1f}% RAM'
            })
        
        return recommendation
    
    def log_scaling_decision(self, recommendation: Dict[str, Any]):
        """Registra la decisión de escalado"""
        config = recommendation['config']
        system_load = config['system_load']
        
        logger.info("=== DYNAMIC SCALING DECISION ===")
        logger.info(f"Hardware: {config['strategy']}")
        logger.info(f"Current Load: {system_load['cpu_percent']:.1f}% CPU, {system_load['memory_percent']:.1f}% RAM")
        logger.info(f"Queue Length: {config['queue_factor']}")
        logger.info(f"Workers: {recommendation['current_workers']} → {recommendation['recommended_workers']}")
        logger.info(f"Action: {recommendation['action']} - {recommendation['reason']}")
        logger.info(f"n_jobs: {config['n_jobs']}")
        if config['safety_applied']:
            logger.warning("Safety limits applied - system near capacity")
        logger.info("=" * 40)

# Instancia global
dynamic_scaler = DynamicScalingPolicy()