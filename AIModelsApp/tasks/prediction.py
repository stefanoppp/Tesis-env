from ..base_imports import *
import pickle
from pycaret.classification import load_model as load_classification_model
from pycaret.regression import load_model as load_regression_model
@shared_task(bind=True)
def make_prediction_task(self, prediction_id):
    try:
        from ..models import Prediction
        
        prediction = Prediction.objects.get(id=prediction_id)
        ai_model = prediction.ai_model
        
        # Cargar el modelo entrenado
        model_path = ai_model.model_file_path.replace('.pkl', '')  # PyCaret agrega .pkl automáticamente
        
        # Determinar tipo de modelo por el tipo de procesamiento del CSV
        processing_type = ai_model.csv_source.processing_type
        
        if processing_type == 'classification':
            model = load_classification_model(model_path)
            result = model.predict(pd.DataFrame([prediction.input_data]))
            
            # Para clasificación, también obtener probabilidades
            probabilities = model.predict_proba(pd.DataFrame([prediction.input_data]))
            max_probability = float(max(probabilities[0]))
            
            prediction_result = {
                'predicted_class': str(result[0]),
                'probabilities': probabilities[0].tolist(),
                'confidence': max_probability
            }
            prediction.confidence_score = max_probability
            
        else:  # regression
            model = load_regression_model(model_path)
            result = model.predict(pd.DataFrame([prediction.input_data]))
            
            prediction_result = {
                'predicted_value': float(result[0])
            }
            prediction.confidence_score = None  # No aplica para regresión
        
        prediction.prediction_result = prediction_result
        prediction.save()
        
        logger.info(f"Predicción {prediction_id} completada")
        
    except Exception as e:
        prediction = Prediction.objects.get(id=prediction_id)
        prediction.prediction_result = {'error': str(e)}
        prediction.save()
        logger.error(f"Error predicción {prediction_id}: {str(e)}")