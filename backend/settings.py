from pathlib import Path
from decouple import config
# === BASE ===

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "django-insecure-xsx2oij5v@hrne9%2vq$1ow&k(y4_nxw0qzz&vd)_92+ccwr68"
DEBUG = True
ALLOWED_HOSTS = []

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

    # Propias
    'UsersApp',
    "PreprocessingApp"
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

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# === REST FRAMEWORK ===

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}
SIMPLE_JWT = {
    'UPDATE_LAST_LOGIN': True,
}
# === CORS ===

CORS_ALLOW_ALL_ORIGINS = True

# === CELERY ===

CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
USE_CELERY_FOR_2FA = True


# === REDIS (para 2FA) ===

REDIS_HOST = 'localhost'
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

# Para testear las pruebas de cada app, supone la de users, se hace asi: python manage.py test UsersApp
# Por ultimo Django, el server de Django
# -----
#--------------------------------Preprocessing APP

import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'PreprocessingApp': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
