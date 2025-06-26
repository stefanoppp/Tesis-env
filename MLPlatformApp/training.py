from celery import shared_task
from .models import AIModel
import pandas as pd
import logging
import os
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def train_model_task(self, model_id, csv_data, ai_model_name):
    """Task para entrenar modelo con PyCaret"""
    try:
        ai_model = AIModel.objects.get(id=model_id)
        ai_model.status = 'training'
        ai_model.progress = 10
        ai_model.save()
        
        logger.info(f"Starting training for model {model_id}")
        
        # Convertir datos de vuelta a DataFrame
        df = pd.DataFrame(csv_data)
        target_column = ai_model.target_column
        task_type = ai_model.task_type
        
        ai_model.progress = 20
        ai_model.save()
        
        # Importar PyCaret según el tipo de tarea
        if task_type == 'classification':
            from pycaret.classification import setup, compare_models, tune_model, save_model
            sort_metric = 'Accuracy'
        else:
            from pycaret.regression import setup, compare_models, tune_model, save_model
            sort_metric = 'MAE'
        
        # Setup de PyCaret
        setup(
            data=df,
            target=target_column,
            session_id=123,
            verbose=False,
            normalize=True,
            transformation=True,
            remove_multicollinearity=True,
            imputation_type='simple',
            numeric_imputation='mean',
            categorical_imputation='mode',
            remove_outliers=True,
        )
        
        ai_model.progress = 40
        ai_model.save()
        
        # Comparar modelos
        best_model = compare_models()
        
        ai_model.progress = 70
        ai_model.save()

        tuned_model=tune_model(best_model, optimize=sort_metric)
        # Crear directorio y guardar modelo
        model_dir = f"media/models/{ai_model.user.username}/"
        os.makedirs(model_dir, exist_ok=True)

        # Usar el nombre que eligió el usuario (sin espacios ni caracteres especiales)
        safe_name = ai_model.name.replace(' ', '_').replace('-', '_')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '_')
        model_path = f"{model_dir}{safe_name}_{model_id[:8]}"

        save_model(tuned_model, model_path)  # ← Usar model_path, no ai_model_name

        # Actualizar modelo en BD
        ai_model.model_path = model_path + '.pkl'
        ai_model.status = 'completed'
        ai_model.progress = 100
        ai_model.save()
        
        logger.info(f"Model {model_id} training completed successfully")
        return f"Model {model_id} training completed"
        
    except Exception as e:
        ai_model = AIModel.objects.get(id=model_id)
        ai_model.status = 'failed'
        ai_model.save()
        logger.error(f"Training failed for model {model_id}: {str(e)}")
        raise