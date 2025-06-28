from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import AIModel, PredictionLog
from .training import train_model_task
import pandas as pd
import os
import tempfile
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
            
            # ACEPTAR AMBOS NOMBRES DE CAMPO PARA IGNORED_COLUMNS
            ignored_columns = (
                request.data.get('ignored_columns', []) or 
                request.data.get('ignore_columns', [])
            )
            
            # Asegurar que sea una lista
            if isinstance(ignored_columns, str):
                ignored_columns = [ignored_columns] if ignored_columns else []
            
            # Parámetros adicionales
            is_public = request.data.get('is_public', False)
            
            logging.info(f"Ignored columns received from frontend: {ignored_columns}")
            
            # 3. VALIDACIONES MÍNIMAS
            if not model_name:
                return Response({'error': 'name is required'}, status=400)
            if not target_column:
                return Response({'error': 'target_column is required'}, status=400)
            if not task_type or task_type not in ['classification', 'regression']:
                return Response({'error': 'task_type must be "classification" or "regression"'}, status=400)
            if target_column not in df.columns:
                return Response({'error': f'Target column "{target_column}" not found'}, status=400)
            
            # Validar que las columnas a ignorar existan
            if ignored_columns:
                invalid_cols = [col for col in ignored_columns if col not in df.columns]
                if invalid_cols:
                    return Response({
                        'error': f'Ignored columns not found in dataset: {invalid_cols}',
                        'available_columns': list(df.columns)
                    }, status=400)
            
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
            
            # 5. GUARDAR CSV TEMPORALMENTE
            csv_file.seek(0)
            
            # Crear directorio temporal para el usuario
            temp_dir = f"media/temp/{request.user.username}/"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Guardar archivo CSV con nombre único
            temp_csv_path = f"{temp_dir}{ai_model.id}.csv"
            with open(temp_csv_path, 'wb+') as destination:
                for chunk in csv_file.chunks():
                    destination.write(chunk)
            
            # 6. LANZAR ENTRENAMIENTO
            train_model_task.delay(
                model_id=str(ai_model.id),
                csv_file_path=temp_csv_path,
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
            # Intentar obtener modelo propio primero
            ai_model = None
            is_owner = False
            
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
            
            # Respuesta básica
            response = {
                'id': str(ai_model.id),
                'name': ai_model.name,
                'status': ai_model.status,
                'progress': ai_model.progress,
                'created_at': ai_model.created_at,
                'is_owner': is_owner,
                'owner': ai_model.user.username,
                'is_public': ai_model.is_public
            }
            
            # Información adicional solo para owners
            if is_owner:
                response.update({
                    'task_type': ai_model.task_type,
                    'dataset_name': ai_model.dataset_name,
                    'target_column': ai_model.target_column,
                    'description': ai_model.description
                })
                
                # Mostrar errores solo al owner
                if ai_model.status == 'failed' and hasattr(ai_model, 'error_message'):
                    response['error_message'] = ai_model.error_message
            
            return Response(response)
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)

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
            
            # Obtener datos de entrada
            input_data = request.data.get('input_data', {})
            
            # Validar que input_data no esté vacío
            if not input_data:
                return Response({
                    'error': 'Missing input_data in request body',
                    'required_structure': {
                        'input_data': {
                            feature: 'value' for feature in ai_model.features_list[:3]
                        }
                    },
                    'all_required_features': ai_model.features_list,
                    'note': 'Send a POST request with input_data containing all required features'
                }, status=400)
            
            # Validar features faltantes
            missing_features = set(ai_model.features_list) - set(input_data.keys())
            if missing_features:
                # Crear ejemplo con valores placeholder
                example_data = {}
                for feature in ai_model.features_list:
                    if feature in input_data:
                        example_data[feature] = input_data[feature]  # Mantener valores existentes
                    else:
                        # Sugerir valores de ejemplo según el nombre
                        if any(word in feature.lower() for word in ['type', 'class', 'category']):
                            example_data[feature] = 'example_category'
                        elif any(word in feature.lower() for word in ['name', 'id']):
                            example_data[feature] = 'example_name'
                        elif any(word in feature.lower() for word in ['generation', 'year', 'age']):
                            example_data[feature] = 1
                        else:
                            example_data[feature] = 100  # Valor numérico por defecto
                
                return Response({
                    'error': 'Missing required features for prediction',
                    'missing_features': sorted(list(missing_features)),
                    'features_provided': sorted(list(input_data.keys())) if input_data else [],
                    'required_request_format': {
                        'input_data': example_data
                    },
                    'instructions': [
                        '1. Send a POST request to this endpoint',
                        '2. Include "input_data" in the request body',
                        '3. Provide values for ALL required features',
                        f'4. This model needs {len(ai_model.features_list)} features total'
                    ],
                    'all_required_features': ai_model.features_list
                }, status=400)
            
            # Hacer predicción
            result = self._make_prediction(ai_model, input_data)
            
            # GUARDAR LOG DE PREDICCIÓN (sin validar límites)
            prediction_log = PredictionLog.objects.create(
                ai_model=ai_model,
                user=request.user,
                input_data=input_data,
                prediction_result=result,
                confidence=result.get('confidence'),
                is_public_model=ai_model.is_public and not is_owner
            )
            
            logging.info(f"Prediction log created: {prediction_log.id} for user {request.user.username}")
            
            return Response({
                'prediction_id': str(prediction_log.id),
                'model_id': str(ai_model.id),
                'model_name': ai_model.name,
                'is_public': ai_model.is_public,
                'is_owner': is_owner,
                'owner': ai_model.user.username,
                'input_data': input_data,
                'prediction': result,
                'task_type': ai_model.task_type
            })
            
        except Exception as e:
            logging.error(f"PredictView error: {str(e)}")
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
                # Estadísticas generales del modelo
                total_predictions = PredictionLog.objects.filter(ai_model=model).count()
                unique_users = PredictionLog.objects.filter(ai_model=model).values('user').distinct().count()
                
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
                        'unique_users': unique_users
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
                'required_features': ai_model.features_list,
                'target_column': ai_model.target_column,
                'metrics': self._get_metrics(ai_model)
            }
            
            return Response(response)
            
        except Exception as e:
            logging.error(f"ModelInfoView error: {str(e)}")
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