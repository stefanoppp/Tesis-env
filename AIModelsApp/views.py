from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import AIModel, Prediction
from .serializers import AIModelSerializer
from .tasks.main import train_ai_model
from .tasks.prediction import make_prediction_task

class CreateModelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = AIModelSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            ai_model = serializer.save(user=request.user)
            train_ai_model.delay(ai_model.id)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

class MyModelsListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        models = AIModel.objects.filter(user=request.user)
        serializer = AIModelSerializer(models, many=True)
        return Response(serializer.data)

class ModelStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, model_id):
        try:
            model = AIModel.objects.get(id=model_id, user=request.user)
            return Response({
                'status': model.status,
                'progress': model.progress,
                'error_message': model.error_message
            })
        except AIModel.DoesNotExist:
            return Response({'error': 'Modelo no encontrado'}, status=404)

class ModelMetricsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, model_id):
        try:
            model = AIModel.objects.get(id=model_id, user=request.user)
            return Response({
                'metrics': model.model_metrics,
                'training_time': model.training_time_seconds,
                'dataset_size': model.dataset_size
            })
        except AIModel.DoesNotExist:
            return Response({'error': 'Modelo no encontrado'}, status=404)

class PredictView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, model_id):
        try:
            # Verificar que el modelo existe y pertenece al usuario
            ai_model = AIModel.objects.get(id=model_id, user=request.user)
            
            # Verificar que el modelo está entrenado
            if ai_model.status != 'completed':
                return Response({
                    'error': 'El modelo no está entrenado aún',
                    'status': ai_model.status,
                    'progress': ai_model.progress
                }, status=400)
            
            # Obtener input_data del request
            input_data = request.data.get('input_data', {})
            
            # HACER PREDICCIÓN DIRECTAMENTE
            from pycaret.classification import load_model as load_classification_model
            from pycaret.regression import load_model as load_regression_model
            import pandas as pd
            
            # Cargar el modelo
            model_path = ai_model.model_file_path.replace('.pkl', '')
            processing_type = ai_model.csv_source.processing_type
            
            # Convertir input_data a DataFrame
            input_df = pd.DataFrame([input_data])
            
            if processing_type == 'classification':
                model = load_classification_model(model_path)
                prediction_result = model.predict(input_df)
                
                # Verificar si el modelo tiene predict_proba
                try:
                    probabilities = model.predict_proba(input_df)
                    confidence = float(max(probabilities[0]))
                    
                    result = {
                        'predicted_class': str(prediction_result[0]),
                        'probabilities': probabilities[0].tolist(),
                        'confidence': confidence,
                        'prediction_type': 'classification'
                    }
                except AttributeError:
                    # Algunos clasificadores como RidgeClassifier no tienen predict_proba
                    result = {
                        'predicted_class': str(prediction_result[0]),
                        'probabilities': None,
                        'confidence': None,
                        'prediction_type': 'classification',
                        'note': 'Este modelo no proporciona probabilidades'
                    }
                    confidence = None
                
            else:  # regression
                model = load_regression_model(model_path)
                prediction_result = model.predict(input_df)
                
                result = {
                    'predicted_value': float(prediction_result[0]),
                    'prediction_type': 'regression'
                }
                confidence = None
            
            # Guardar en base de datos
            prediction = Prediction.objects.create(
                ai_model=ai_model,
                user=request.user,
                input_data=input_data,
                prediction_result=result,
                confidence_score=confidence
            )
            
            return Response({
                'prediction_id': prediction.id,
                'ai_model': ai_model.name,
                'input_data': input_data,
                'result': result,
                'confidence_score': confidence,
                'model_metrics': ai_model.model_metrics,
                'status': 'completed'
            }, status=200)
            
        except AIModel.DoesNotExist:
            return Response({'error': 'Modelo no encontrado'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        
class MarketplaceView(APIView):
    def get(self, request):
        models = AIModel.objects.filter(is_public=True, status='completed')
        serializer = AIModelSerializer(models, many=True)
        return Response(serializer.data)