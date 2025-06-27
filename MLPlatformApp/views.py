from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import AIModel, PredictionLog
from .training import train_model_task
import pandas as pd
import os
import tempfile
import os
import logging
class CreateModelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # 1. VALIDAR ARCHIVO CSV
            if 'file' not in request.FILES:
                return Response({'error': 'CSV file is required'}, status=400)
            
            csv_file = request.FILES['file']
            df = pd.read_csv(csv_file)
            
            # 2. OBTENER PARÁMETROS BÁSICOS
            model_name = request.data.get('name')
            target_column = request.data.get('target_column')
            task_type = request.data.get('task_type')
            ignored_columns = request.data.get('ignored_columns', [])
            # Parametros aparte
            is_public = request.data.get('is_public')
            # 3. VALIDACIONES MÍNIMAS
            if not model_name:
                return Response({'error': 'name is required'}, status=400)
            if not target_column:
                return Response({'error': 'target_column is required'}, status=400)
            if not task_type or task_type not in ['classification', 'regression']:
                return Response({'error': 'task_type must be "classification" or "regression"'}, status=400)
            if target_column not in df.columns:
                return Response({'error': f'Target column "{target_column}" not found'}, status=400)
            
            # 4. CREAR MODELO EN BD
            ai_model = AIModel.objects.create(
                user=request.user,
                name=model_name,
                task_type=task_type,
                target_column=target_column,
                dataset_name=csv_file.name,
                is_public=is_public,
                description=request.data.get('description', ''),
            )
            
            # 5. GUARDAR CSV TEMPORALMENTE - SOLUCIÓN PRINCIPAL
            csv_file.seek(0)
            
            # Crear directorio temporal para el usuario
            temp_dir = f"media/temp/{request.user.username}/"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Guardar archivo CSV con nombre único
            temp_csv_path = f"{temp_dir}{ai_model.id}.csv"
            with open(temp_csv_path, 'wb+') as destination:
                for chunk in csv_file.chunks():
                    destination.write(chunk)
            
            # 6. LANZAR ENTRENAMIENTO con ruta del archivo
            train_model_task.delay(
                model_id=str(ai_model.id),
                csv_file_path=temp_csv_path,  # Pasar ruta en lugar de datos
                target_column=target_column,
                ignored_columns=ignored_columns,
                task_type=task_type,
            )
            
            return Response({
                'id': str(ai_model.id),
                'message': 'Model training started',
                'name': model_name,
                'status': 'pending'
            }, status=201)
            
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class ModelStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, model_id):
        try:
            ai_model = AIModel.objects.get(id=model_id, user=request.user)
            
            return Response({
                'id': str(ai_model.id),
                'name': ai_model.name,
                'status': ai_model.status,
                'progress': ai_model.progress,
                'created_at': ai_model.created_at
            })
            
        except AIModel.DoesNotExist:
            return Response({'error': 'Model not found'}, status=404)

class MyModelsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Obtener todos los modelos del usuario autenticado
            models = AIModel.objects.filter(user=request.user)
            
            models_data = []
            for model in models:
                models_data.append({
                    'id': str(model.id),
                    'name': model.name,
                    'description': model.description,
                    'task_type': model.task_type,
                    'dataset_name': model.dataset_name,
                    'target_column': model.target_column,
                    'features_count': len(model.features_list),
                    'status': model.status,
                    'progress': model.progress,
                    'is_public': model.is_public,
                    'created_at': model.created_at,
                    'model_path': model.model_path if model.status == 'completed' else None
                })
            
            return Response({
                'count': len(models_data),
                'models': models_data
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)

class PredictView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, model_id):
        try:
            # Intentar obtener modelo (privado o público)
            ai_model = None
            is_owner = False
            
            # Verificar si es owner
            try:
                ai_model = AIModel.objects.get(id=model_id, user=request.user)
                is_owner = True
            except AIModel.DoesNotExist:
                # Si no es owner, intentar como público
                try:
                    ai_model = AIModel.objects.get(id=model_id, is_public=True)
                    is_owner = False
                except AIModel.DoesNotExist:
                    return Response({'error': 'Model not found or access denied'}, status=404)
            
            # Verificar que el modelo esté entrenado
            if ai_model.status != 'completed':
                return Response({
                    'error': 'Model not ready',
                    'status': ai_model.status,
                    'progress': ai_model.progress
                }, status=400)
            
            # RATE LIMITING PARA MODELOS PÚBLICOS
            if not is_owner and ai_model.is_public:
                today = timezone.now().date()
                today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
                
                # Contar predicciones del usuario hoy en este modelo
                predictions_today = PredictionLog.objects.filter(
                    user=request.user,
                    ai_model=ai_model,
                    created_at__gte=today_start
                ).count()
                
                if predictions_today >= 10:  # Límite diario
                    return Response({
                        'error': 'Daily prediction limit reached for this public model',
                        'limit': 10,
                        'used_today': predictions_today,
                        'reset_time': 'midnight'
                    }, status=429)
            
            # Obtener datos de entrada
            input_data = request.data.get('input_data', {})
            
            # Validar features
            missing_features = set(ai_model.features_list) - set(input_data.keys())
            if missing_features:
                return Response({
                    'error': 'Missing features',
                    'missing': list(missing_features),
                    'required_features': ai_model.features_list
                }, status=400)
            
            # Hacer predicción
            result = self._make_prediction(ai_model, input_data)
            
            # GUARDAR LOG DE PREDICCIÓN
            prediction_log = PredictionLog.objects.create(
                ai_model=ai_model,
                user=request.user,
                input_data=input_data,
                prediction_result=result,
                confidence=result.get('confidence'),
                is_public_model=ai_model.is_public and not is_owner
            )
            
            # Calcular predicciones restantes solo si no es owner
            remaining_predictions = None
            if not is_owner and ai_model.is_public:
                today = timezone.now().date()
                today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
                predictions_today = PredictionLog.objects.filter(
                    user=request.user,
                    ai_model=ai_model,
                    created_at__gte=today_start
                ).count()
                remaining_predictions = 10 - predictions_today
            
            return Response({
                'prediction_id': str(prediction_log.id),
                'model_id': str(ai_model.id),
                'model_name': ai_model.name,
                'is_public': ai_model.is_public,
                'is_owner': is_owner,
                'owner': ai_model.user.username,
                'input_data': input_data,
                'prediction': result,
                'task_type': ai_model.task_type,
                'remaining_predictions': remaining_predictions
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    
    def _make_prediction(self, ai_model, input_data):
        """Hacer predicción usando el modelo guardado"""
        import pandas as pd
        
        # Importar según tipo de tarea
        if ai_model.task_type == 'classification':
            from pycaret.classification import load_model as load_classification_model
            model = load_classification_model(ai_model.model_path.replace('.pkl', ''))
        else:
            from pycaret.regression import load_model as load_regression_model  
            model = load_regression_model(ai_model.model_path.replace('.pkl', ''))
        
        # Convertir input a DataFrame
        input_df = pd.DataFrame([input_data])
        
        # Hacer predicción
        prediction = model.predict(input_df)
        
        if ai_model.task_type == 'classification':
            try:
                probabilities = model.predict_proba(input_df)
                confidence = float(max(probabilities[0]))
                
                return {
                    'predicted_class': str(prediction[0]),
                    'probabilities': probabilities[0].tolist(),
                    'confidence': confidence
                }
            except:
                return {
                    'predicted_class': str(prediction[0]),
                    'probabilities': None,
                    'confidence': None
                }
        else:
            return {
                'predicted_value': float(prediction[0])
            }

class DeleteModelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, model_id):
        try:
            ai_model = AIModel.objects.get(id=model_id, user=request.user)
            model_name = ai_model.name
            
            # Eliminar modelo (esto también eliminará el archivo físico)
            ai_model.delete()
            
            return Response({
                'message': f'Model "{model_name}" deleted successfully'
            })
            
        except AIModel.DoesNotExist:
            return Response({'error': 'Model not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        
class PublicModelsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Obtener todos los modelos públicos completados
            public_models = AIModel.objects.filter(is_public=True, status='completed')
            
            models_data = []
            for model in public_models:
                # Contar predicciones totales del modelo
                total_predictions = PredictionLog.objects.filter(ai_model=model).count()
                
                # Contar usuarios únicos que han usado el modelo
                unique_users = PredictionLog.objects.filter(ai_model=model).values('user').distinct().count()
                
                # Verificar si el usuario actual ya usó este modelo hoy
                today = timezone.now().date()
                today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
                user_predictions_today = PredictionLog.objects.filter(
                    ai_model=model,
                    user=request.user,
                    created_at__gte=today_start
                ).count()
                
                models_data.append({
                    'id': str(model.id),
                    'name': model.name,
                    'description': model.description,
                    'owner': model.user.username,
                    'task_type': model.task_type,
                    'dataset_name': model.dataset_name,
                    'target_column': model.target_column,
                    'features_count': len(model.features_list),
                    'features_list': model.features_list,
                    'created_at': model.created_at,
                    'statistics': {
                        'total_predictions': total_predictions,
                        'unique_users': unique_users,
                        'user_predictions_today': user_predictions_today,
                        'remaining_predictions': 10 - user_predictions_today
                    }
                })
            
            return Response({
                'count': len(models_data),
                'public_models': models_data
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        
class ModelInfoView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, model_id):
        try:
            # Obtener modelo (privado o público)
            ai_model = None
            is_owner = False
            
            try:
                ai_model = AIModel.objects.get(id=model_id, user=request.user)
                is_owner = True
            except AIModel.DoesNotExist:
                try:
                    ai_model = AIModel.objects.get(id=model_id, is_public=True)
                    is_owner = False
                except AIModel.DoesNotExist:
                    return Response({'error': 'Model not found'}, status=404)
            
            if ai_model.status != 'completed':
                return Response({'error': 'Model not ready', 'status': ai_model.status}, status=400)
            
            # DATOS BÁSICOS
            response = {
                'model_id': str(ai_model.id),
                'model_name': ai_model.name,
                'task_type': ai_model.task_type,
                'owner': ai_model.user.username,
                'is_owner': is_owner,
                
                # PARÁMETROS REQUERIDOS
                'required_features': ai_model.features_list,
                'target_column': ai_model.target_column,
                
                # MÉTRICAS + INTERPRETACIÓN
                'metrics': self._get_metrics(ai_model)
            }
            
            # RATE LIMIT (solo para modelos públicos)
            if not is_owner and ai_model.is_public:
                today = timezone.now().date()
                today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
                used_today = PredictionLog.objects.filter(
                    ai_model=ai_model, user=request.user, created_at__gte=today_start
                ).count()
                
                response['remaining_predictions'] = 10 - used_today
            
            return Response(response)
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    
    def _get_metrics(self, ai_model):
        """Obtener métricas guardadas durante entrenamiento"""
        try:
            # LEER MÉTRICAS DESDE LA BASE DE DATOS
            if ai_model.model_metrics and len(ai_model.model_metrics) > 0:
                logging.info(f"Loading metrics from database for model {ai_model.id}")
                return ai_model.model_metrics
            else:
                logging.warning(f"No metrics found in database for model {ai_model.id}")
                return {
                    'error': 'No metrics available - model may have been trained before metrics feature',
                    'model_type': 'unknown',
                    'available': False,
                    'note': 'Train a new model to get detailed metrics'
                }
                
        except Exception as e:
            logging.error(f"Error reading metrics from database: {str(e)}")
            return {
                'error': f'Error loading metrics: {str(e)}',
                'model_type': 'unknown',
                'available': False
            }
    
    def _extract_classification_metrics(self, df, model):
        """Métricas de clasificación"""
        try:
            metrics = {
                'model_type': type(model).__name__,
                'accuracy': round(float(df.iloc[0]['Accuracy']), 4),
                'precision': round(float(df.iloc[0]['Prec.']), 4),
                'recall': round(float(df.iloc[0]['Recall']), 4),
                'f1_score': round(float(df.iloc[0]['F1']), 4),
                'auc': round(float(df.iloc[0]['AUC']), 4) if 'AUC' in df.columns else None,
            }
            
            # INTERPRETACIÓN SIMPLE
            acc = metrics['accuracy']
            metrics['interpretation'] = {
                'accuracy_level': 'Excelente' if acc >= 0.9 else 'Muy Bueno' if acc >= 0.8 else 'Bueno' if acc >= 0.7 else 'Regular',
                'model_quality': 'Alta' if acc >= 0.85 else 'Media' if acc >= 0.7 else 'Baja',
                'reliability': f'{int(acc*100)}% de precisión'
            }
            
            return metrics
            
        except Exception as e:
            return {'error': f'Classification metrics error: {str(e)}'}
    
    def _extract_regression_metrics(self, df, model):
        """Métricas de regresión"""
        try:
            metrics = {
                'model_type': type(model).__name__,
                'r2': round(float(df.iloc[0]['R2']), 4),
                'mae': round(float(df.iloc[0]['MAE']), 4),
                'rmse': round(float(df.iloc[0]['RMSE']), 4),
                'mape': round(float(df.iloc[0]['MAPE']), 4) if 'MAPE' in df.columns else None,
            }
            
            # INTERPRETACIÓN SIMPLE
            r2 = metrics['r2']
            metrics['interpretation'] = {
                'fit_quality': 'Excelente' if r2 >= 0.9 else 'Muy Bueno' if r2 >= 0.8 else 'Bueno' if r2 >= 0.7 else 'Regular',
                'variance_explained': f'{int(r2*100)}% de la varianza explicada',
                'prediction_accuracy': 'Alta' if r2 >= 0.8 else 'Media' if r2 >= 0.6 else 'Baja'
            }
            
            return metrics
            
        except Exception as e:
            return {'error': f'Regression metrics error: {str(e)}'}