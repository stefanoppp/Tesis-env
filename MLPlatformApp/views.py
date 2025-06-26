from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import AIModel, PredictionLog
from .training import train_model_task
import pandas as pd

class CreateModelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # Validar archivo CSV
            if 'file' not in request.FILES:
                return Response({'error': 'CSV file is required'}, status=400)
            
            csv_file = request.FILES['file']
            df = pd.read_csv(csv_file)
            
            # Obtener parámetros
            target_column = request.data['target_column']
            ignore_columns = request.data.get('ignore_columns', '')
            is_public = request.data.get('is_public', 'false').lower() == 'true'  # Convertir string a bool
            model_name = request.data['name']
            
            print(f"DEBUG: model_name={model_name}, is_public={is_public}")
            
            # Validar que target_column existe
            if target_column not in df.columns:
                return Response({
                    'error': f'Target column "{target_column}" not found',
                    'available_columns': list(df.columns)
                }, status=400)
            
            # VALIDAR NOMBRE SEGÚN VISIBILIDAD
            if is_public:
                # Para público: verificar que no exista ningún modelo público con ese nombre
                existing_public = AIModel.objects.filter(name=model_name, is_public=True)
                print(f"DEBUG: Found {existing_public.count()} public models with name '{model_name}'")
                if existing_public.exists():
                    return Response({
                        'error': f'A public model with name "{model_name}" already exists',
                        'suggestion': f'Try "{model_name}_v2" or choose a different name',
                        'existing_models': [{'id': str(m.id), 'owner': m.user.username} for m in existing_public]
                    }, status=400)
            else:
                # Para privado: verificar solo en modelos del usuario
                existing_private = AIModel.objects.filter(user=request.user, name=model_name)
                print(f"DEBUG: Found {existing_private.count()} private models for user {request.user.username} with name '{model_name}'")
                if existing_private.exists():
                    return Response({
                        'error': f'You already have a model named "{model_name}"',
                        'suggestion': f'Try "{model_name}_v2" or choose a different name',
                        'existing_models': [{'id': str(m.id), 'created_at': m.created_at} for m in existing_private]
                    }, status=400)
            
            # Procesar columnas a ignorar
            ignored_list = []
            if ignore_columns:
                ignored_list = [col.strip() for col in ignore_columns.split(',') if col.strip()]
            
            # Obtener features (todas excepto target e ignoradas)
            features_list = [col for col in df.columns 
                           if col != target_column and col not in ignored_list]
            
            # Crear modelo
            ai_model = AIModel.objects.create(
                user=request.user,
                name=model_name,
                description=request.data.get('description', ''),
                task_type=request.data['task_type'],
                dataset_name=csv_file.name,
                target_column=target_column,
                features_list=features_list,
                is_public=is_public,
            )
            
            # Convertir DataFrame a dict para pasarlo a Celery
            df_cleaned = df.drop(columns=ignored_list, errors='ignore')
            csv_data = df_cleaned.to_dict('records')
            
            # Lanzar task de entrenamiento
            train_model_task.delay(str(ai_model.id), csv_data, ai_model.name)
            
            return Response({
                'id': str(ai_model.id),
                'message': 'Model training started',
                'status': ai_model.status,
                'is_public': is_public,
                'features': features_list,
                'ignored_columns': ignored_list,
                'dataset_shape': df.shape
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