from celery import shared_task
from .models import AIModel
import pandas as pd
import logging
import os

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def train_model_task(self, model_id, csv_file_path, target_column, ignored_columns, task_type):
    """Task corregida para entrenar modelo con PyCaret y guardar métricas"""
    ai_model = None
    
    try:
        ai_model = AIModel.objects.get(id=model_id)
        ai_model.status = 'training'
        ai_model.progress = 10
        ai_model.save()
        
        logger.info(f"Starting training for model {model_id}")
        
        # 1. CARGAR DATOS DESDE ARCHIVO
        data = pd.read_csv(csv_file_path)
        logger.info(f"Dataset shape: {data.shape}")
        
        # VALIDACIÓN BÁSICA
        if task_type == 'regression':
            numeric_cols = data.select_dtypes(include='number').columns.tolist()
            if len(numeric_cols) < 2:
                raise ValueError("El CSV debe tener al menos 2 columnas numéricas para regresión")
            
            if target_column not in numeric_cols:
                raise ValueError(f"La columna target '{target_column}' debe ser numérica para regresión")
        
        logger.info(f"Using '{target_column}' as target column")
        logger.info(f"Data types: {data.dtypes.to_dict()}")
        
        ai_model.progress = 20
        ai_model.save()
        
        # 2. IMPORTAR PYCARET SEGÚN TIPO
        if task_type == 'classification':
            from pycaret.classification import setup, compare_models, save_model, pull
        else:
            from pycaret.regression import setup, compare_models, save_model, pull
        
        # 3. SETUP DE PYCARET
        logger.info("Setting up PyCaret...")
        logger.info(f"Ignoring columns: {ignored_columns}")
        setup(
            data=data,
            target=target_column,
            ignore_features=ignored_columns,
            remove_multicollinearity=True,
            remove_outliers=True,
            imputation_type="simple",
            numeric_imputation="mean",
            categorical_imputation="mode",
            normalize=True,
            verbose=False,
            session_id=123
        ) 
        logger.info("PyCaret setup completed successfully")
        
        ai_model.progress = 50
        ai_model.save()
        
        # 4. COMPARAR MODELOS Y OBTENER MÉTRICAS
        logger.info("Comparing all models...")
        best_model = compare_models(verbose=False)
        
        # OBTENER MÉTRICAS AUTOMÁTICAMENTE DESDE PYCARET
        try:
            metrics_df = pull()  # Obtiene las métricas del compare_models
            logger.info(f"Metrics dataframe shape: {metrics_df.shape}")
            logger.info(f"Available columns: {list(metrics_df.columns)}")
            
            # EXTRAER Y GUARDAR MÉTRICAS SEGÚN EL TIPO
            if task_type == 'classification':
                model_metrics = {
                    'model_type': str(type(best_model).__name__),
                    'accuracy': round(float(metrics_df.iloc[0]['Accuracy']), 4),
                    'precision': round(float(metrics_df.iloc[0]['Prec.']), 4),
                    'recall': round(float(metrics_df.iloc[0]['Recall']), 4),
                    'f1_score': round(float(metrics_df.iloc[0]['F1']), 4),
                    'auc': round(float(metrics_df.iloc[0]['AUC']), 4) if 'AUC' in metrics_df.columns else None,
                    'kappa': round(float(metrics_df.iloc[0]['Kappa']), 4) if 'Kappa' in metrics_df.columns else None,
                    'training_time': round(float(metrics_df.iloc[0]['TT (Sec)']), 2) if 'TT (Sec)' in metrics_df.columns else None,
                    
                    # INTERPRETACIÓN AUTOMÁTICA
                    'interpretation': {
                        'accuracy_level': 'Excelente' if float(metrics_df.iloc[0]['Accuracy']) >= 0.9 else 'Muy Bueno' if float(metrics_df.iloc[0]['Accuracy']) >= 0.8 else 'Bueno' if float(metrics_df.iloc[0]['Accuracy']) >= 0.7 else 'Regular',
                        'model_quality': 'Alta' if float(metrics_df.iloc[0]['Accuracy']) >= 0.85 else 'Media' if float(metrics_df.iloc[0]['Accuracy']) >= 0.7 else 'Baja',
                        'reliability': f"{int(float(metrics_df.iloc[0]['Accuracy'])*100)}% de precisión"
                    }
                }
            else:  # regression
                model_metrics = {
                    'model_type': str(type(best_model).__name__),
                    'r2': round(float(metrics_df.iloc[0]['R2']), 4),
                    'mae': round(float(metrics_df.iloc[0]['MAE']), 4),
                    'rmse': round(float(metrics_df.iloc[0]['RMSE']), 4),
                    'mape': round(float(metrics_df.iloc[0]['MAPE']), 4) if 'MAPE' in metrics_df.columns else None,
                    'training_time': round(float(metrics_df.iloc[0]['TT (Sec)']), 2) if 'TT (Sec)' in metrics_df.columns else None,
                    
                    # INTERPRETACIÓN AUTOMÁTICA
                    'interpretation': {
                        'fit_quality': 'Excelente' if float(metrics_df.iloc[0]['R2']) >= 0.9 else 'Muy Bueno' if float(metrics_df.iloc[0]['R2']) >= 0.8 else 'Bueno' if float(metrics_df.iloc[0]['R2']) >= 0.7 else 'Regular',
                        'variance_explained': f"{int(float(metrics_df.iloc[0]['R2'])*100)}% de la varianza explicada",
                        'prediction_accuracy': 'Alta' if float(metrics_df.iloc[0]['R2']) >= 0.8 else 'Media' if float(metrics_df.iloc[0]['R2']) >= 0.6 else 'Baja'
                    }
                }
            
            logger.info(f"Model metrics extracted: {model_metrics}")
            
        except Exception as metrics_error:
            logger.warning(f"Could not extract metrics: {metrics_error}")
            model_metrics = {
                'model_type': str(type(best_model).__name__) if 'best_model' in locals() else 'unknown',
                'error': str(metrics_error),
                'available': False
            }
        
        ai_model.progress = 80
        ai_model.save()
        
        # 5. GUARDAR MODELO
        logger.info("Saving model...")
        model_dir = f"media/models/{ai_model.user.username}/"
        os.makedirs(model_dir, exist_ok=True)
        
        safe_name = ai_model.name.replace(' ', '_').replace('-', '_')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '_')
        model_path = f"{model_dir}{safe_name}_{model_id[:8]}"
        
        save_model(best_model, model_path)
        logger.info(f"Model saved to: {model_path}.pkl")
        
        # 6. ACTUALIZAR BD CON MÉTRICAS
        final_features = [col for col in data.columns 
                        if col != target_column and col not in ignored_columns]

        logger.info(f"Target column: {target_column}")
        logger.info(f"Ignored columns: {ignored_columns}")
        logger.info(f"Final features: {final_features}")

        ai_model.model_path = model_path + '.pkl'
        ai_model.features_list = final_features
        ai_model.model_metrics = model_metrics
        ai_model.status = 'completed'
        ai_model.progress = 100
        ai_model.save()
        # 7. LIMPIAR ARCHIVO TEMPORAL
        try:
            if os.path.exists(csv_file_path):
                os.remove(csv_file_path)
                logger.info(f"Temporary file {csv_file_path} removed")
        except Exception as cleanup_error:
            logger.warning(f"Could not remove temporary file {csv_file_path}: {cleanup_error}")
        
        logger.info(f"Model {ai_model.name} training completed successfully!")
        logger.info(f"Final metrics: {model_metrics}")
        
        return f"Model '{ai_model.name}' training completed"
        
    except Exception as e:
        # MANEJO DE ERRORES
        error_message = str(e)
        logger.error(f"Training failed for model {model_id}: {error_message}")
        
        # Limpiar archivo temporal
        try:
            if 'csv_file_path' in locals() and os.path.exists(csv_file_path):
                os.remove(csv_file_path)
                logger.info("Temporary file cleaned up after error")
        except:
            pass
        
        # Actualizar modelo como fallido
        if ai_model:
            try:
                ai_model.status = 'failed'
                ai_model.progress = 0
                ai_model.error_message = error_message[:500]  # Truncar si es muy largo
                ai_model.save()
                logger.info(f"Model {model_id} marked as failed")
            except Exception as db_error:
                logger.error(f"Could not update model status: {str(db_error)}")
        
        # Re-lanzar el error para Celery
        raise Exception(f"Training failed: {error_message}")