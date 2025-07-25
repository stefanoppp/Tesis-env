from pathlib import Path
from decouple import config
from datetime import timedelta
import os
# === BASE ===

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "django-insecure-xsx2oij5v@hrne9%2vq$1ow&k(y4_nxw0qzz&vd)_92+ccwr68"
DEBUG = True
ALLOWED_HOSTS = []
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # Donde Django guarda los archivos con collectstatic
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),  # Carpeta local para desarrollo opcional
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media') 
# === APPS ===

INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Terceros
    'rest_framework',
    'corsheaders',
    'django_celery_beat',

    # Propias
    'UsersApp',
    'MLPlatformApp',
]

# === MIDDLEWARE ===

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # debe ir antes de CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'MLPlatformApp.middleware.SystemLoadMiddleware',  # Monitoreo de carga del sistema
]

# === URLS Y WSGI ===

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# === BASE DE DATOS ===

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# === VALIDACIÓN DE CONTRASEÑAS ===

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# === INTERNACIONALIZACIÓN ===

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# === ARCHIVOS ESTÁTICOS ===


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# === REST FRAMEWORK ===

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

# Configuración JWT para extensión automática de sesión
SIMPLE_JWT = {
    'UPDATE_LAST_LOGIN': True,
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),  # Token de acceso válido por 30 minutos
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),     # Refresh token válido por 7 días
    'ROTATE_REFRESH_TOKENS': True,                   # Rota el refresh token en cada uso
    'BLACKLIST_AFTER_ROTATION': True,               # Invalida el refresh token anterior
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# Configuración para extensión automática de sesión
SESSION_EXTENSION_SETTINGS = {
    'ACTIVITY_TIMEOUT': 15 * 60,          # 15 minutos de inactividad antes de logout
    'ACTIVITY_CHECK_INTERVAL': 5 * 60,    # Verificar actividad cada 5 minutos
    'EXTEND_ON_ACTIVITY': True,            # Extender sesión en actividad
}
# === CORS ===

CORS_ALLOW_ALL_ORIGINS = True

# === CELERY ===

CELERY_BROKER_URL = "redis://redis:6379/0"
CELERY_RESULT_BACKEND = "redis://redis:6379/0"
REDIS_HOST = "redis"
REDIS_PORT = 6379
REDIS_DB = 0
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Configuración de colas y routing
CELERY_TASK_DEFAULT_QUEUE = 'training'
CELERY_TASK_ROUTES = {
    'MLPlatformApp.training.train_model_task': {'queue': 'training'},
}

# Configuraciones básicas de Celery worker
CELERY_WORKER_STATE_DB = None  # Deshabilitar state db para evitar errores
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_LOG_COLOR = False

# Configuración automática de Celery con escalado dinámico
try:
    from MLPlatformApp.config.celery_config import get_celery_config, get_dynamic_celery_config, log_celery_recommendations
    from MLPlatformApp.config.dynamic_scaling import dynamic_scaler
    import os
    
    # Verificar si el escalado dinámico está habilitado
    dynamic_scaling_enabled = os.getenv('DYNAMIC_SCALING_ENABLED', 'true').lower() == 'true'
    
    if dynamic_scaling_enabled:
        # Usar configuración dinámica (se ajusta según carga actual)
        celery_config = get_dynamic_celery_config(queue_length=0)  # Configuración inicial
        print("[CELERY] Escalado dinámico HABILITADO - Configuración se ajustará automáticamente")
    else:
        # Usar configuración estática optimizada
        celery_config = get_celery_config()
        print("[CELERY] Escalado dinámico DESHABILITADO - Usando configuración estática")
    
    # Aplicar configuración de Celery
    CELERY_WORKER_CONCURRENCY = celery_config['worker_concurrency']
    CELERY_WORKER_PREFETCH_MULTIPLIER = celery_config['worker_prefetch_multiplier']
    CELERY_TASK_ACKS_LATE = celery_config['task_acks_late']
    CELERY_WORKER_MAX_TASKS_PER_CHILD = celery_config['worker_max_tasks_per_child']
    CELERY_TASK_SOFT_TIME_LIMIT = celery_config['task_soft_time_limit']
    CELERY_TASK_TIME_LIMIT = celery_config['task_time_limit']
    CELERY_WORKER_DISABLE_RATE_LIMITS = celery_config['worker_disable_rate_limits']
    CELERY_TASK_REJECT_ON_WORKER_LOST = celery_config['task_reject_on_worker_lost']
    
    # Configuraciones adicionales para escalado dinámico
    if dynamic_scaling_enabled:
        # Límites de seguridad del sistema
        CPU_THRESHOLD = int(os.getenv('CPU_THRESHOLD', '80'))
        MEMORY_THRESHOLD = int(os.getenv('MEMORY_THRESHOLD', '80'))
        
        # Configurar autoscale de Celery
        optimal_workers, scaling_config = dynamic_scaler.calculate_optimal_workers(0)
        max_workers = scaling_config['max_workers']
        min_workers = 1
        
        # Variables para autoscale
        CELERY_WORKER_AUTOSCALER = f'{max_workers},{min_workers}'
        CELERY_WORKER_AUTOSCALE_MAX = max_workers
        CELERY_WORKER_AUTOSCALE_MIN = min_workers
        
        print(f"[CELERY] Autoscale configurado: {min_workers}-{max_workers} workers")
        print(f"[CELERY] Límites de seguridad: CPU<{CPU_THRESHOLD}%, RAM<{MEMORY_THRESHOLD}%")
        print(f"[CELERY] Estrategia: {scaling_config['strategy']}")
    
    # Registrar recomendaciones en los logs
    log_celery_recommendations()
    
except ImportError as e:
    print(f"[CELERY] Error importando configuración dinámica: {e}")
    # Configuración por defecto si no está disponible el optimizador
    CELERY_WORKER_CONCURRENCY = 2
    CELERY_WORKER_PREFETCH_MULTIPLIER = 1
    CELERY_TASK_ACKS_LATE = True
    CELERY_WORKER_MAX_TASKS_PER_CHILD = 10
    CELERY_WORKER_AUTOSCALER = '4,1'  # Fallback autoscale
    print("[CELERY] Usando configuración por defecto con autoscale básico")


# === REDIS (para 2FA) ===

REDIS_HOST = 'redis'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_2FA_EXPIRE_SECONDS = 600  # 10 minutos
REDIS_2FA_MAX_ATTEMPTS = 3

# === EMAIL (SMTP REAL) ===

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587

EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
EMAIL_USE_TLS = True
REDIS_2FA_MAX_ATTEMPTS = 3


# === OPCIONAL: para desarrollo rápido (comentar smtp arriba y descomentar esto) ===
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Primero levantamos el entorno de django, luego Redis con docker container, 
# luego Celery. Para eso hay que pararse en /tesis y hacer:celery -A backend worker --loglevel=info --pool=solo
# Sino tambien puede ser: python -m celery -A backend worker --loglevel=info --pool=solo


# Para testear las pruebas de cada app, supone la de users, se hace asi: python manage.py test UsersApp
# Por ultimo Django, el server de Django
# -----

# === CONFIGURACIÓN ML PLATFORM ===

# Configuración de la plataforma ML
ML_PLATFORM_SETTINGS = {
    # Sistema de colas
    'MAX_CONCURRENT_TRAINING': 3,
    'ESTIMATED_TRAINING_TIME_MINUTES': 30,
    'PRIORITY_BOOST_PREMIUM': True,
    
    # Límites de cola y rate limiting
    'MAX_GLOBAL_QUEUE_SIZE': 20,  # Máximo modelos pendientes globalmente
    'MAX_USER_PENDING_MODELS': 3,  # Máximo modelos pendientes por usuario
    'QUEUE_RETRY_AFTER_SECONDS': 300,  # 5 minutos
    
    # Límites del sistema (ahora configurados automáticamente)
    'MAX_CPU_PERCENT': 70,
    'MAX_MEMORY_PERCENT': 70,
    'CLEANUP_FAILED_MODELS_DAYS': 7,
    
    # Configuración automática de hardware
    'AUTO_HARDWARE_OPTIMIZATION': True,
    'ENABLE_GPU_ACCELERATION': True,
    
    # Configuración de paginación
    'DEFAULT_PAGE_SIZE': 15,
    'MAX_PAGE_SIZE': 100,
    
    # Límites de operaciones masivas
    'MAX_BULK_DELETE_MODELS': 100,
}

# === CONFIGURACIÓN DE ESCALADO DINÁMICO ===

# Habilitar/deshabilitar escalado dinámico
DYNAMIC_SCALING_ENABLED = os.getenv('DYNAMIC_SCALING_ENABLED', 'true').lower() == 'true'

# Límites de seguridad del sistema (porcentajes)
CPU_THRESHOLD = int(os.getenv('CPU_THRESHOLD', '80'))
MEMORY_THRESHOLD = int(os.getenv('MEMORY_THRESHOLD', '80'))

# Configuración del middleware de monitoreo
SYSTEM_MONITORING_SETTINGS = {
    'CHECK_INTERVAL_SECONDS': 30,  # Verificar carga cada 30 segundos
    'LOW_LOAD_CPU_THRESHOLD': 50,  # CPU < 50% = baja carga
    'LOW_LOAD_MEMORY_THRESHOLD': 50,  # RAM < 50% = baja carga
    'ENABLE_SCALE_UP_RECOMMENDATIONS': True,
    'ENABLE_SCALE_DOWN_ENFORCEMENT': True,
    'LOG_SYSTEM_METRICS': True,
}

# Configuración de logging para escalado dinámico
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'scaling.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'MLPlatformApp.middleware': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'MLPlatformApp.config.dynamic_scaling': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Crear directorio de logs si no existe
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

print(f"[SISTEMA] Escalado dinámico: {'HABILITADO' if DYNAMIC_SCALING_ENABLED else 'DESHABILITADO'}")
print(f"[SISTEMA] Límites de seguridad: CPU<{CPU_THRESHOLD}%, RAM<{MEMORY_THRESHOLD}%")
print(f"[SISTEMA] Middleware de monitoreo: ACTIVO")