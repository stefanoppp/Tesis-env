from ..base_imports import *
from .train_classification import train_classification_model
from .train_regression import train_regression_model
from io import StringIO
import time

@shared_task(bind=True)
def train_ai_model(self, model_id):
    try:
        ai_model = AIModel.objects.get(id=model_id)
        ai_model.status = 'training'
        ai_model.progress = 10
        ai_model.save()
        
        # Obtener datos del CSV preprocesado
        csv_source = ai_model.csv_source
        
        # LEER EL ARCHIVO PROCESADO (no processed_data)
        df = pd.read_csv(csv_source.processed_file.path)  # ← Cambio aquí
        
        # Obtener configuración del CSV
        target_column = csv_source.target_column
        processing_type = csv_source.processing_type
        ignored_columns = csv_source.drop_column  # ← Es drop_column, no ignored_columns
        
        # Filtrar columnas ignoradas si existen
        if ignored_columns:
            # Convertir string separado por comas a lista
            ignored_list = [col.strip() for col in ignored_columns.split(',') if col.strip()]
            df = df.drop(columns=ignored_list, errors='ignore')
        
        ai_model.progress = 20
        ai_model.save()
        
        start_time = time.time()
        
        # Entrenar según tipo, pasando los 3 parámetros
        if processing_type == 'classification':
            result = train_classification_model(ai_model, df, target_column)
        else:
            result = train_regression_model(ai_model, df, target_column)
        
        # Guardar resultados
        ai_model.best_model_name = result['model_name']
        ai_model.model_file_path = result['model_path']
        ai_model.training_time_seconds = time.time() - start_time
        ai_model.dataset_size = len(df)
        ai_model.status = 'completed'
        ai_model.progress = 100
        ai_model.completed_at = timezone.now()
        ai_model.save()
        
        logger.info(f"Modelo {model_id} completado")
        
    except Exception as e:
        ai_model = AIModel.objects.get(id=model_id)
        ai_model.status = 'failed'
        ai_model.error_message = str(e)
        ai_model.save()
        logger.error(f"Error modelo {model_id}: {str(e)}")