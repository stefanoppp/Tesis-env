from .hardware_optimization import hardware_optimizer
from .dynamic_scaling import dynamic_scaler
import logging
import os

logger = logging.getLogger(__name__)

def get_celery_config():
    """
    Obtiene la configuración optimizada para Celery basada en el hardware disponible.
    
    Returns:
        dict: Configuración de Celery optimizada
    """
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

def get_dynamic_celery_config(queue_length: int = 0):
    """
    Obtiene configuración dinámica de Celery basada en carga actual del sistema.
    
    Args:
        queue_length: Número de tareas en cola
        
    Returns:
        dict: Configuración de Celery optimizada dinámicamente
    """
    try:
        # Obtener configuración base
        base_config = get_celery_config()
        
        # Calcular workers óptimos según carga actual
        optimal_workers, scaling_config = dynamic_scaler.calculate_optimal_workers(queue_length)
        
        # Actualizar configuración con escalado dinámico
        dynamic_config = base_config.copy()
        dynamic_config.update({
            'worker_concurrency': optimal_workers,
            'scaling_info': scaling_config,
            'dynamic_scaling_enabled': True
        })
        
        # Configuración de autoscale para Celery
        max_workers = scaling_config.get('max_workers', optimal_workers + 2)
        min_workers = max(1, optimal_workers - 1)
        dynamic_config['worker_autoscaler'] = (max_workers, min_workers)
        
        # Configuración de pool
        dynamic_config['worker_pool'] = 'solo'
        
        # Configuración de enrutamiento de tareas
        dynamic_config['task_routes'] = {
            'MLPlatformApp.training.train_model_task': {'queue': 'training'},
            'MLPlatformApp.tasks.*': {'queue': 'default'},
        }
        
        # Ajustar otros parámetros según la carga
        system_load = scaling_config['system_load']
        
        # Si el sistema está sobrecargado, ser más conservador
        if system_load['cpu_percent'] > 70 or system_load['memory_percent'] > 70:
            dynamic_config.update({
                'worker_prefetch_multiplier': 1,  # No prefetch cuando hay sobrecarga
                'task_soft_time_limit': int(dynamic_config['task_soft_time_limit'] * 0.8),  # Reducir tiempo límite
                'worker_max_tasks_per_child': 5  # Reiniciar workers más frecuentemente
            })
        
        logger.info(f"Dynamic scaling: {optimal_workers} workers for queue_length={queue_length}, "
                    f"CPU={system_load['cpu_percent']:.1f}%, RAM={system_load['memory_percent']:.1f}%")
        
        return dynamic_config
        
    except Exception as e:
        logger.error(f"Error in get_dynamic_celery_config: {e}")
        # Devolver configuración por defecto en caso de error
        fallback_config = get_celery_config()
        fallback_config.update({
            'worker_autoscaler': (4, 1),
            'worker_pool': 'solo',
            'task_routes': {
                'MLPlatformApp.training.train_model_task': {'queue': 'training'},
                'MLPlatformApp.tasks.*': {'queue': 'default'},
            },
            'dynamic_scaling_enabled': False,
            'scaling_info': {'error': str(e)}
        })
        return fallback_config

def get_scaling_recommendation(current_workers: int, queue_length: int = 0):
    """
    Obtiene recomendación de escalado para workers actuales.
    
    Args:
        current_workers: Número actual de workers
        queue_length: Número de tareas en cola
        
    Returns:
        dict: Recomendación de escalado
    """
    recommendation = dynamic_scaler.get_scaling_recommendation(current_workers, queue_length)
    dynamic_scaler.log_scaling_decision(recommendation)
    return recommendation

def log_celery_recommendations():
    """
    Registra recomendaciones para la configuración de Celery.
    """
    config = hardware_optimizer.get_optimal_config()
    
    logger.info("=== CELERY CONFIGURATION RECOMMENDATIONS ===")
    logger.info(f"Recommended concurrency: {config['recommended_concurrency']}")
    logger.info(f"Hardware type: {'GPU-accelerated' if config['use_gpu'] else 'CPU-only'}")
    logger.info(f"Available CPU cores: {config['cpu_count']}")
    logger.info(f"Available RAM: {config['memory_gb']:.1f} GB")
    
    if config['use_gpu']:
        logger.info("GPU detected - using conservative concurrency to avoid conflicts")
    else:
        logger.info("No GPU detected - optimizing for CPU performance")
    
    # Mostrar configuración de escalado dinámico
    optimal_workers, scaling_config = dynamic_scaler.calculate_optimal_workers(0)
    logger.info("\n=== DYNAMIC SCALING POLICY ===")
    logger.info(f"Strategy: {scaling_config['strategy']}")
    logger.info(f"Base workers: {optimal_workers}")
    logger.info(f"Max workers: {scaling_config['max_workers']}")
    logger.info(f"n_jobs per task: {scaling_config['n_jobs']}")
    logger.info(f"CPU threshold: 80%, Memory threshold: 80%")
    
    logger.info("\nTo apply these settings, update your Celery worker command:")
    logger.info(f"celery -A your_project worker --concurrency={optimal_workers} --loglevel=info")
    logger.info("=" * 50)