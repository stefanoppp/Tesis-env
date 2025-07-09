# API Configuration - Bulk Operations
from django.conf import settings

# Límites para operaciones masivas
BULK_DELETE_LIMITS = {
    'MAX_MODELS_PER_REQUEST': getattr(settings, 'MAX_BULK_DELETE_MODELS', 100),
    'RATE_LIMIT_PER_MINUTE': getattr(settings, 'BULK_DELETE_RATE_LIMIT', 10),
    'TIMEOUT_SECONDS': getattr(settings, 'BULK_DELETE_TIMEOUT', 30),
}

# Headers de respuesta para indicar el método usado
RESPONSE_HEADERS = {
    'X-Delete-Method': 'DELETE',  # o 'POST' dependiendo del método usado
    'X-Bulk-Operation': 'true',
    'X-Operation-Count': '',  # número de elementos procesados
}

# Códigos de error específicos
ERROR_CODES = {
    'INVALID_MODEL_IDS': 'BULK_001',
    'PERMISSION_DENIED': 'BULK_002', 
    'MODELS_NOT_FOUND': 'BULK_003',
    'LIMIT_EXCEEDED': 'BULK_004',
    'OPERATION_FAILED': 'BULK_005',
}

# Logging configuration
BULK_OPERATIONS_LOG_FORMAT = {
    'user_id': '',
    'operation': 'bulk_delete_models',
    'method': '',  # DELETE o POST
    'model_ids': [],
    'success_count': 0,
    'error_count': 0,
    'timestamp': '',
    'duration_ms': 0,
}
