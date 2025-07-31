# MLPlatformApp Configuration Package
# Este paquete contiene la configuración optimizada para hardware

from .hardware_optimization import hardware_optimizer
from .celery_config import get_celery_config

__all__ = [
    'hardware_optimizer',
    'get_celery_config'
]