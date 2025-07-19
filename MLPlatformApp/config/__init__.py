# MLPlatformApp Configuration Package
# Este paquete contiene la configuración optimizada para hardware y escalado dinámico

from .hardware_optimization import hardware_optimizer
from .dynamic_scaling import dynamic_scaler
from .celery_config import (
    get_celery_config,
    get_dynamic_celery_config,
    get_scaling_recommendation,
    log_celery_recommendations
)

__all__ = [
    'hardware_optimizer',
    'dynamic_scaler',
    'get_celery_config',
    'get_dynamic_celery_config',
    'get_scaling_recommendation',
    'log_celery_recommendations'
]