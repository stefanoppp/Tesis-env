import logging
import pandas as pd
from celery import shared_task
from AIModelsApp.models import AIModel  # Cambiar a import absoluto según el nombre de la app
from django.utils import timezone
import os
from pathlib import Path
from django.conf import settings

logger = logging.getLogger('AIModelsApp')

# Directorio base para guardar modelos
MODELS_BASE_DIR = Path(settings.BASE_DIR) / 'media' / 'ai_models'
MODELS_BASE_DIR.mkdir(parents=True, exist_ok=True)

def get_model_path(user, model_type, model_name, model_id):
    """
    Crea la estructura de carpetas: /ai_models/user/model_type/model_name/
    """
    model_dir = MODELS_BASE_DIR / user.username / model_type / f"{model_name}_{model_id}"
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir / "model"