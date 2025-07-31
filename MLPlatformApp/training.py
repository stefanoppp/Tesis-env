from celery import shared_task
from .models import AIModel
from .config.hardware_optimization import hardware_optimizer
import pandas as pd
import logging
import os
import time

logger = logging.getLogger(__name__)

@shared_task(bind=True,queue="training")
def train_model_task(self, model_id, csv_file_path, target_column, ignored_columns, task_type):
    """Task corregida para entrenar modelo con PyCaret y guardar métricas"""
    ai_model = None
    
    try:
        # Verificar si el modelo existe antes de proceder
        try:
            ai_model = AIModel.objects.get(id=model_id)
        except AIModel.DoesNotExist:
            logger.error(f"Model with ID {model_id} does not exist. Skipping training.")
            return {"error": f"Model {model_id} not found", "status": "skipped"}
        
        ai_model = AIModel.objects.get(id=model_id)
        ai_model.status = 'training'
        ai_model.progress = 10
        ai_model.save()
        
        # Iniciar timer de entrenamiento
        training_start_time = time.time()
        
        logger.info(f"Starting training for model {model_id}")
        
        # 1. CARGAR DATOS DESDE ARCHIVO
        data = pd.read_csv(csv_file_path)
        logger.info(f"Dataset shape: {data.shape}")
        
        # LIMPIAR VALORES NULOS EN LA COLUMNA TARGET
        initial_rows = len(data)
        data = data.dropna(subset=[target_column])
        final_rows = len(data)
        
        if final_rows < initial_rows:
            logger.info(f"Eliminadas {initial_rows - final_rows} filas con valores nulos en la columna target '{target_column}'")
            logger.info(f"Dataset shape después de limpiar target: {data.shape}")
        
        if len(data) == 0:
            raise ValueError(f"No quedan datos después de eliminar valores nulos de la columna target '{target_column}'")
        
        # VALIDACIÓN BÁSICA
        if task_type == 'regression':
            numeric_cols = data.select_dtypes(include='number').columns.tolist()
            if len(numeric_cols) < 2:
                raise ValueError("El CSV debe tener al menos 2 columnas numéricas para regresión")
            
            if target_column not in numeric_cols:
                raise ValueError(f"La columna target '{target_column}' debe ser numérica para regresión")
        
        # VALIDACIÓN CRÍTICA PARA CLASIFICACIÓN
        if task_type == 'classification':
            class_counts = data[target_column].value_counts()
            min_class_count = class_counts.min()
            classes_with_one_sample = class_counts[class_counts == 1]
            
            if len(classes_with_one_sample) > 0:
                logger.warning(f"ADVERTENCIA: Dataset con clases problemáticas detectado.")
                logger.warning(f"Clases con solo 1 muestra: {classes_with_one_sample.to_dict()}")
                logger.warning(f"Esto puede causar problemas durante el entrenamiento.")
                
                # Si hay demasiadas clases con 1 muestra, rechazar el dataset
                if len(classes_with_one_sample) > len(class_counts) * 0.3:  # Más del 30% de clases problemáticas
                    raise ValueError(f"Dataset inválido: {len(classes_with_one_sample)} clases tienen solo 1 muestra. Esto representa el {len(classes_with_one_sample)/len(class_counts)*100:.1f}% de las clases. Por favor, proporcione un dataset con más muestras por clase para un entrenamiento efectivo.")
        
        logger.info(f"Using '{target_column}' as target column")
        logger.info(f"Data types: {data.dtypes.to_dict()}")
        
        ai_model.progress = 20
        ai_model.save()
        
        # 2. IMPORTAR PYCARET SEGÚN TIPO
        if task_type == 'classification':
            from pycaret.classification import setup, compare_models, save_model, pull
        else:
            from pycaret.regression import setup, compare_models, save_model, pull
        
        # 3. SETUP DE PYCARET CON OPTIMIZACIONES AUTOMÁTICAS
        logger.info("Setting up PyCaret with hardware optimization...")
        logger.info(f"Ignoring columns: {ignored_columns}")
        
        # Obtener configuración optimizada según hardware
        hardware_optimizer.log_system_info()
        config = hardware_optimizer.get_optimal_config()
        
        # VERIFICAR DISTRIBUCIÓN DE CLASES ANTES DEL SETUP PARA AJUSTAR CV_FOLDS
        if task_type == 'classification':
            # Contar muestras por clase
            class_counts = data[target_column].value_counts()
            min_class_count = class_counts.min()
            total_samples = len(data)
            
            logger.info(f"Distribución de clases: {class_counts.to_dict()}")
            logger.info(f"Clase con menos muestras: {min_class_count}")
            logger.info(f"Total de muestras: {total_samples}")
            
            # VALIDACIÓN CRÍTICA: Si hay clases con solo 1 muestra, forzar holdout
            if min_class_count < 2:
                logger.error(f"DATASET INVÁLIDO: Hay clases con solo {min_class_count} muestra(s). Esto es insuficiente para entrenamiento.")
                logger.error(f"Clases problemáticas: {class_counts[class_counts < 2].to_dict()}")
                
                # Forzar holdout y train_size alto para evitar problemas
                adjusted_cv_folds = None
                train_size = 0.9  # Usar 90% para entrenamiento
                logger.warning(f"FORZANDO holdout validation con train_size={train_size} debido a clases con 1 muestra.")
                
            elif min_class_count < config['cv_folds']:
                # Si hay clases con pocas muestras, reducir cv_folds
                adjusted_cv_folds = max(min_class_count, 2)  # Mínimo 2 folds
                train_size = 0.8  # Configuración estándar
                logger.warning(f"Clases con pocas muestras detectadas. Reduciendo CV folds de {config['cv_folds']} a {adjusted_cv_folds}")
                
            else:
                adjusted_cv_folds = config['cv_folds']
                train_size = 0.8  # Configuración estándar
                logger.info(f"Distribución de clases adecuada. Usando {adjusted_cv_folds} CV folds")
        else:
            # Para regresión, usar configuración normal
            adjusted_cv_folds = config['cv_folds']
            train_size = 0.8
            logger.info(f"Tarea de regresión. Usando {adjusted_cv_folds} CV folds")
        
        # Configuración optimizada según hardware disponible
        setup_params = {
            'data': data,
            'target': target_column,
            'ignore_features': ignored_columns,
            'remove_multicollinearity': True,
            'remove_outliers': True,
            'imputation_type': "simple",
            'numeric_imputation': "mean",
            'categorical_imputation': "mode",
            'normalize': True,
            'verbose': False,
            'n_jobs': config['n_jobs'],
            'session_id': 123,
            'train_size': train_size  # Tamaño de entrenamiento ajustado
        }
        
        # Agregar fold solo si no es None (para evitar holdout cuando hay clases con 1 muestra)
        if adjusted_cv_folds is not None:
            setup_params['fold'] = adjusted_cv_folds
            logger.info(f"Usando {adjusted_cv_folds}-fold cross validation con train_size={train_size}")
        else:
            logger.info(f"Usando holdout validation con train_size={train_size} debido a clases con pocas muestras")
        
        # Agregar configuración GPU si está disponible
        if config['use_gpu']:
            setup_params['use_gpu'] = True
            logger.info(f"GPU enabled with {config['n_jobs']} CPU jobs")
        else:
            logger.info(f"CPU-only mode with {config['n_jobs']} jobs")
        
        setup(**setup_params) 
        logger.info("PyCaret setup completed successfully")
        
        ai_model.progress = 50
        ai_model.save()
        
        # 4. COMPARAR MODELOS CON CONFIGURACIÓN OPTIMIZADA
        logger.info("Comparing models with hardware-optimized configuration...")
        
        # Seleccionar modelos según el tipo de tarea
        if task_type == 'classification':
            selected_models = config['preferred_models_classification']
            logger.info("Using CLASSIFICATION models")
        else:
            selected_models = config['preferred_models_regression']
            logger.info("Using REGRESSION models")
        
        # La verificación de distribución de clases ya se hizo antes del setup
        
        # Usar configuración optimizada según hardware
        compare_params = {
            'include': selected_models,
            'verbose': False,
            'n_select': 1,
            'budget_time': config['budget_time']  # Tiempo MÁXIMO por modelo durante comparación
        }
        
        # Agregar fold solo si no es None (para evitar holdout cuando hay clases con 1 muestra)
        if adjusted_cv_folds is not None:
            compare_params['fold'] = adjusted_cv_folds
        else:
            logger.info("Usando holdout validation debido a clases con pocas muestras")
        
        logger.info(f"Selected {len(selected_models)} models: {selected_models}")
        logger.info(f"CV folds: {adjusted_cv_folds if adjusted_cv_folds is not None else 'holdout'}")
        logger.info(f"Budget time: {config['budget_time']} min MÁXIMO por modelo durante comparación")
        logger.info("NOTA: 'budget_time' es el tiempo LÍMITE por modelo en compare_models(), no el tiempo real")
        
        best_model = compare_models(**compare_params)
        
        # Calcular tiempo real de entrenamiento hasta este punto
        training_end_time = time.time()
        actual_training_time = round(training_end_time - training_start_time, 2)
        
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
                    'training_time': actual_training_time,
                    
                    # INTERPRETACIÓN AUTOMÁTICA BASADA EN ESTÁNDARES ACADÉMICOS
                    # Criterios según Sokolova & Lapalme (2009) y Hosmer & Lemeshow (2000)
                    'interpretation': {
                        'accuracy_level': 'Excelente' if float(metrics_df.iloc[0]['Accuracy']) >= 0.9 else 'Bueno' if float(metrics_df.iloc[0]['Accuracy']) >= 0.8 else 'Aceptable' if float(metrics_df.iloc[0]['Accuracy']) >= 0.7 else 'Pobre',
                        'precision_level': 'Excelente' if float(metrics_df.iloc[0]['Prec.']) >= 0.9 else 'Bueno' if float(metrics_df.iloc[0]['Prec.']) >= 0.8 else 'Aceptable' if float(metrics_df.iloc[0]['Prec.']) >= 0.7 else 'Pobre',
                        'recall_level': 'Excelente' if float(metrics_df.iloc[0]['Recall']) >= 0.9 else 'Bueno' if float(metrics_df.iloc[0]['Recall']) >= 0.8 else 'Aceptable' if float(metrics_df.iloc[0]['Recall']) >= 0.7 else 'Pobre',
                        'f1_level': 'Excelente' if float(metrics_df.iloc[0]['F1']) >= 0.9 else 'Bueno' if float(metrics_df.iloc[0]['F1']) >= 0.8 else 'Aceptable' if float(metrics_df.iloc[0]['F1']) >= 0.7 else 'Pobre',
                        'auc_level': 'Excelente discriminación' if 'AUC' in metrics_df.columns and float(metrics_df.iloc[0]['AUC']) >= 0.9 else 'Buena discriminación' if 'AUC' in metrics_df.columns and float(metrics_df.iloc[0]['AUC']) >= 0.8 else 'Discriminación aceptable' if 'AUC' in metrics_df.columns and float(metrics_df.iloc[0]['AUC']) >= 0.7 else 'Pobre discriminación' if 'AUC' in metrics_df.columns else 'No disponible',
                        'model_quality': 'Alta' if float(metrics_df.iloc[0]['Accuracy']) >= 0.8 and float(metrics_df.iloc[0]['F1']) >= 0.8 else 'Media' if float(metrics_df.iloc[0]['Accuracy']) >= 0.7 and float(metrics_df.iloc[0]['F1']) >= 0.7 else 'Baja',
                        'reliability': f"{int(float(metrics_df.iloc[0]['Accuracy'])*100)}% de exactitud global",
                        'standard_used': 'Sokolova Lapalme 2009 IEEE'
                    }
                }
            else:  # regression
                model_metrics = {
                    'model_type': str(type(best_model).__name__),
                    'r2': round(float(metrics_df.iloc[0]['R2']), 4),
                    'mae': round(float(metrics_df.iloc[0]['MAE']), 4),
                    'rmse': round(float(metrics_df.iloc[0]['RMSE']), 4),
                    'mape': round(float(metrics_df.iloc[0]['MAPE']), 4) if 'MAPE' in metrics_df.columns else None,
                    'training_time': actual_training_time,
                    
                    # INTERPRETACIÓN AUTOMÁTICA BASADA EN ESTÁNDARES ACADÉMICOS
                    # Criterios según Cohen (1988) y Hosmer & Lemeshow (2000)
                    'interpretation': {
                        'r2_level': 'Excelente ajuste' if float(metrics_df.iloc[0]['R2']) >= 0.9 else 'Buen ajuste' if float(metrics_df.iloc[0]['R2']) >= 0.8 else 'Ajuste moderado' if float(metrics_df.iloc[0]['R2']) >= 0.5 else 'Ajuste pobre',
                        'mae_interpretation': f"Error promedio de {round(float(metrics_df.iloc[0]['MAE']), 2)} unidades",
                        'rmse_interpretation': f"Error cuadrático medio de {round(float(metrics_df.iloc[0]['RMSE']), 2)} unidades",
                        'variance_explained': f"{int(float(metrics_df.iloc[0]['R2'])*100)}% de la varianza explicada",
                        'prediction_quality': 'Alta' if float(metrics_df.iloc[0]['R2']) >= 0.8 else 'Media' if float(metrics_df.iloc[0]['R2']) >= 0.5 else 'Baja',
                        'model_strength': 'Muy fuerte' if float(metrics_df.iloc[0]['R2']) >= 0.9 else 'Fuerte' if float(metrics_df.iloc[0]['R2']) >= 0.8 else 'Moderado' if float(metrics_df.iloc[0]['R2']) >= 0.5 else 'Débil',
                        'standard_used': 'Cohen 1988 Statistical Power Analysis'
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
        
        # 5. GUARDAR MODELO Y ESTADÍSTICAS DE IMPUTACIÓN
        logger.info("Saving model...")
        model_dir = f"media/models/{ai_model.user.username}/"
        os.makedirs(model_dir, exist_ok=True)
        
        safe_name = ai_model.name.replace(' ', '_').replace('-', '_')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '_')
        model_path = f"{model_dir}{safe_name}_{model_id[:8]}"
        
        # Guardar estadísticas de imputación para usar en predicciones
        try:
            imputation_stats = {}
            
            # Obtener estadísticas del dataset de entrenamiento para imputación
            for column in data.columns:
                if column != target_column and column not in ignored_columns:
                    if data[column].dtype in ['int64', 'float64']:
                        # Para columnas numéricas, usar la media
                        imputation_stats[column] = float(data[column].mean())
                    else:
                        # Para columnas categóricas, usar la moda
                        mode_value = data[column].mode()
                        if len(mode_value) > 0:
                            imputation_stats[column] = str(mode_value.iloc[0])
                        else:
                            imputation_stats[column] = "Valor más común"
            
            # Guardar las estadísticas junto al modelo
            stats_path = f"{model_path}_imputation_stats.pkl"
            import pickle
            with open(stats_path, 'wb') as f:
                pickle.dump(imputation_stats, f)
            
            logger.info(f"Estadísticas de imputación guardadas: {imputation_stats}")
            
        except Exception as e:
            logger.warning(f"No se pudieron guardar las estadísticas de imputación: {str(e)}")
        
        save_model(best_model, model_path)
        logger.info(f"Model saved to: {model_path}.pkl")
        
        # 6. ACTUALIZAR BD CON MÉTRICAS Y TIPOS DE DATOS
        final_features_names = [col for col in data.columns 
                               if col != target_column and col not in ignored_columns]
        
        # Crear lista con nombres y tipos de datos
        final_features = []
        for col in final_features_names:
            dtype = str(data[col].dtype)
            # Simplificar tipos de pandas a categorías más generales
            if dtype.startswith('int') or dtype.startswith('float'):
                data_type = 'numeric'
            elif dtype == 'object':
                # Verificar si es categórico (pocos valores únicos)
                unique_ratio = data[col].nunique() / len(data)
                if unique_ratio < 0.1:  # Menos del 10% de valores únicos
                    data_type = 'categorical'
                else:
                    data_type = 'text'
            elif dtype == 'bool':
                data_type = 'categorical'
            else:
                data_type = 'text'
            
            final_features.append({
                'name': col,
                'data_type': data_type,
                'original_dtype': dtype
            })

        logger.info(f"Target column: {target_column}")
        logger.info(f"Ignored columns: {ignored_columns}")
        logger.info(f"Final features with types: {final_features}")

        ai_model.model_path = model_path + '.pkl'
        ai_model.features_list = final_features
        ai_model.model_metrics = model_metrics
        ai_model.training_time = actual_training_time
        ai_model.status = 'completed'
        ai_model.progress = 100
        ai_model.save()
        
        logger.info(f"Actual training time: {actual_training_time} seconds")
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