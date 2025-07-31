from .hardware_optimization import hardware_optimizer
import logging
import os

logger = logging.getLogger(__name__)

def get_celery_config():
    """
    Obtiene la configuración optimizada para Celery basada en el hardware disponible.
    
    Returns:
        dict: Configuración de Celery optimizada
    """
    # Verificar si la detección de GPU está deshabilitada
    if os.getenv('DISABLE_GPU_DETECTION', '0') == '1':
        logger.info("🚫 Configuración de Celery sin detección de hardware (GPU deshabilitada)")
        # Configuración básica sin detección de hardware
        return {
            'worker_concurrency': 2,
            'worker_prefetch_multiplier': 1,
            'task_acks_late': True,
            'worker_max_tasks_per_child': 10,
            'task_soft_time_limit': 1800,
            'task_time_limit': 2400,
            'worker_disable_rate_limits': False,
            'task_reject_on_worker_lost': True,
        }
    
    config = hardware_optimizer.get_optimal_config()
    
    # Configuración base de Celery
    celery_config = {
        'worker_concurrency': config['recommended_concurrency'],
        'worker_prefetch_multiplier': 1,  # Evitar que los workers tomen demasiadas tareas
        'task_acks_late': True,  # Confirmar tareas solo después de completarlas
        'worker_max_tasks_per_child': 10,  # Reiniciar workers después de 10 tareas
        'task_soft_time_limit': 1800,  # 30 minutos límite suave
        'task_time_limit': 2400,  # 40 minutos límite duro
        'worker_disable_rate_limits': False,
        'task_reject_on_worker_lost': True,
    }
    
    # Configuración específica según hardware
    if config['use_gpu']:
        # Con GPU, reducir concurrencia para evitar conflictos
        celery_config.update({
            'worker_concurrency': min(config['recommended_concurrency'], 2),
            'worker_prefetch_multiplier': 1,
            'task_soft_time_limit': 900,  # 15 minutos con GPU
            'task_time_limit': 1200,  # 20 minutos con GPU
        })
        logger.info(f"Celery configured for GPU: concurrency={celery_config['worker_concurrency']}")
    else:
        # Con CPU, usar configuración conservadora
        celery_config.update({
            'worker_concurrency': config['recommended_concurrency'],
            'worker_prefetch_multiplier': 1,
        })
        logger.info(f"Celery configured for CPU: concurrency={celery_config['worker_concurrency']}")
    
    return celery_config