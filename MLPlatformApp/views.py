from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.core.paginator import Paginator
from django.conf import settings
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
            # 1. VALIDAR ARCHIVO CSV PRIMERO
            if 'file' not in request.FILES:
                return Response({
                    'error': 'Se requiere un archivo CSV',
                    'detail': 'Se requiere un archivo CSV',
                    'error_code': 'MISSING_CSV_FILE',
                    'error_type': 'validation_error'
                }, status=400)
            
            csv_file = request.FILES['file']
            
            # Validar que sea un archivo CSV válido
            try:
                df = pd.read_csv(csv_file)
                if df.empty:
                    return Response({
                        'error': 'El archivo CSV está vacío',
                        'detail': 'El archivo CSV está vacío',
                        'error_code': 'EMPTY_CSV_FILE',
                        'error_type': 'validation_error'
                    }, status=400)
            except Exception as e:
                return Response({
                    'error': f'Error al leer el archivo CSV: {str(e)}',
                    'detail': f'Error al leer el archivo CSV: {str(e)}',
                    'error_code': 'INVALID_CSV_FILE',
                    'error_type': 'validation_error'
                }, status=400)
            
            # 2. Obtener configuración de límites
            ml_settings = getattr(settings, 'ML_PLATFORM_SETTINGS', {})
            max_global_queue = ml_settings.get('MAX_GLOBAL_QUEUE_SIZE', 20)
            max_user_pending = ml_settings.get('MAX_USER_PENDING_MODELS', 3)
            retry_after = ml_settings.get('QUEUE_RETRY_AFTER_SECONDS', 300)
            
            # 3. Verificar límite global de cola
            global_pending_count = AIModel.objects.filter(status='pending').count()
            if global_pending_count >= max_global_queue:
                return Response({
                    'error': f'Sistema temporalmente saturado. Hay {global_pending_count} modelos en cola (máximo {max_global_queue}). Intenta nuevamente en unos minutos.',
                    'detail': f'Sistema temporalmente saturado. Hay {global_pending_count} modelos en cola (máximo {max_global_queue}). Intenta nuevamente en unos minutos.',
                    'error_code': 'QUEUE_LIMIT_EXCEEDED',
                    'error_type': 'queue_limit_error',
                    'retry_after': retry_after,
                    'queue_info': {
                        'global_pending': global_pending_count,
                        'max_queue_size': max_global_queue
                    }
                }, status=429)
            
            # 4. Verificar capacidad del worker (70% máximo)
            import psutil
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory_percent = psutil.virtual_memory().percent
                
                if cpu_percent > 70 or memory_percent > 70:
                    return Response({
                        'error': f'Worker sobrecargado. CPU: {cpu_percent:.1f}%, Memoria: {memory_percent:.1f}%. Límite máximo: 70%. Intenta nuevamente en unos minutos.',
                        'detail': f'Worker sobrecargado. CPU: {cpu_percent:.1f}%, Memoria: {memory_percent:.1f}%. Límite máximo: 70%. Intenta nuevamente en unos minutos.',
                        'error_code': 'WORKER_OVERLOADED',
                        'error_type': 'system_load_error',
                        'worker_info': {
                            'cpu_percent': round(cpu_percent, 1),
                            'memory_percent': round(memory_percent, 1),
                            'cpu_limit': 70,
                            'memory_limit': 70
                        },
                        'retry_after': 120
                    }, status=429)
            except Exception as e:
                logging.warning(f'Error verificando capacidad del worker: {str(e)}')
            
            # 5. Verificar límite de modelos en entrenamiento por usuario (máximo 3)
            user_training_count = AIModel.objects.filter(user=request.user, status='training').count()
            if user_training_count >= 3:
                return Response({
                    'error': f'Has alcanzado el límite de 3 modelos en entrenamiento. Tienes {user_training_count} modelos entrenando. Espera a que terminen los actuales.',
                    'detail': f'Has alcanzado el límite de 3 modelos en entrenamiento. Tienes {user_training_count} modelos entrenando. Espera a que terminen los actuales.',
                    'error_code': 'USER_TRAINING_LIMIT_EXCEEDED',
                    'error_type': 'user_limit_error',
                    'user_training_info': {
                        'training_models': user_training_count,
                        'max_training_models': 3
                    }
                }, status=429)
            
            # 6. Verificar rate limiting por usuario (modelos pendientes)
            user_pending_count = AIModel.objects.filter(user=request.user, status='pending').count()
            if user_pending_count >= max_user_pending:
                return Response({
                    'error': f'Has alcanzado el límite de {max_user_pending} modelos en cola. Tienes {user_pending_count} modelos pendientes. Espera a que se procesen los actuales.',
                    'detail': f'Has alcanzado el límite de {max_user_pending} modelos en cola. Tienes {user_pending_count} modelos pendientes. Espera a que se procesen los actuales.',
                    'error_code': 'USER_QUEUE_LIMIT_EXCEEDED',
                    'error_type': 'user_limit_error',
                    'user_queue_info': {
                        'pending_models': user_pending_count,
                        'max_user_pending': max_user_pending
                    }
                }, status=429)
            
            # 2. OBTENER PARÁMETROS BÁSICOS
            model_name = request.data.get('name')
            target_column = request.data.get('target_column')
            task_type = request.data.get('task_type')
            
            # DEBUGGING COMPLETO PARA VER QUÉ LLEGA
            raw_ignored_1 = request.data.get('ignored_columns')
            raw_ignored_2 = request.data.get('ignore_columns')
            
            logging.info(f"=== DEBUGGING IGNORED COLUMNS ===")
            logging.info(f"ignored_columns field: {raw_ignored_1} (type: {type(raw_ignored_1)})")
            logging.info(f"ignore_columns field: {raw_ignored_2} (type: {type(raw_ignored_2)})")
            logging.info(f"Full request.data: {dict(request.data)}")
            
            # Usar el que no sea None
            raw_ignored = raw_ignored_1 if raw_ignored_1 is not None else raw_ignored_2
            
            # PROCESAR SEGÚN EL TIPO
            if raw_ignored is None or raw_ignored == "":
                ignored_columns = []
                logging.info("ignored_columns is None or empty")
            elif isinstance(raw_ignored, list):
                ignored_columns = [str(col).strip() for col in raw_ignored if str(col).strip()]
                logging.info(f"Processed as list: {ignored_columns}")
            elif isinstance(raw_ignored, str):
                import json
                raw_ignored = raw_ignored.strip()
                
                # Intentar JSON
                if raw_ignored.startswith('[') and raw_ignored.endswith(']'):
                    try:
                        parsed = json.loads(raw_ignored)
                        if isinstance(parsed, list):
                            ignored_columns = [str(col).strip() for col in parsed if str(col).strip()]
                        else:
                            ignored_columns = [str(parsed).strip()] if str(parsed).strip() else []
                        logging.info(f"Parsed JSON successfully: {ignored_columns}")
                    except json.JSONDecodeError as e:
                        logging.error(f"Failed to parse JSON: {raw_ignored}, error: {e}")
                        ignored_columns = []
                # String separado por comas
                elif ',' in raw_ignored:
                    ignored_columns = [col.strip() for col in raw_ignored.split(',') if col.strip()]
                    logging.info(f"Processed as comma-separated: {ignored_columns}")
                # String simple no vacío
                elif raw_ignored:
                    ignored_columns = [raw_ignored]
                    logging.info(f"Processed as single string: {ignored_columns}")
                else:
                    ignored_columns = []
                    logging.info("String is empty after strip")
            else:
                ignored_columns = []
                logging.error(f"Unknown type for ignored_columns: {type(raw_ignored)}")
            
            # Limpiar la lista final
            ignored_columns = [col for col in ignored_columns if col and isinstance(col, str)]
            
            # Parámetros adicionales - Procesar is_public correctamente
            raw_is_public = request.data.get('is_public', False)
            
            # Convertir is_public a booleano de manera robusta
            if isinstance(raw_is_public, str):
                is_public = raw_is_public.lower() in ['true', '1', 'yes', 'on']
            elif isinstance(raw_is_public, (int, float)):
                is_public = bool(raw_is_public)
            else:
                is_public = bool(raw_is_public)
            
            logging.info(f"is_public processing: raw='{raw_is_public}' (type: {type(raw_is_public)}) -> processed={is_public}")
            
            logging.info(f"Final ignored_columns: {ignored_columns}")
            
            # 3. VALIDACIONES MÍNIMAS
            if not model_name:
                return Response({
                    'error': 'El nombre del modelo es requerido',
                    'detail': 'El nombre del modelo es requerido',
                    'error_code': 'MISSING_MODEL_NAME',
                    'error_type': 'validation_error'
                }, status=400)
            if not target_column:
                return Response({
                    'error': 'La columna objetivo es requerida',
                    'detail': 'La columna objetivo es requerida',
                    'error_code': 'MISSING_TARGET_COLUMN',
                    'error_type': 'validation_error'
                }, status=400)
            if not task_type or task_type not in ['classification', 'regression']:
                return Response({
                    'error': 'El tipo de tarea debe ser "classification" o "regression"',
                    'detail': 'El tipo de tarea debe ser "classification" o "regression"',
                    'error_code': 'INVALID_TASK_TYPE',
                    'error_type': 'validation_error'
                }, status=400)
            if target_column not in df.columns:
                return Response({
                    'error': f'La columna objetivo "{target_column}" no se encontró en el dataset',
                    'detail': f'La columna objetivo "{target_column}" no se encontró en el dataset',
                    'error_code': 'TARGET_COLUMN_NOT_FOUND',
                    'error_type': 'validation_error'
                }, status=400)
            
            # Validar que las columnas a ignorar existan
            if ignored_columns:
                invalid_cols = [col for col in ignored_columns if col not in df.columns]
                if invalid_cols:
                    return Response({
                        'error': f'Las siguientes columnas a ignorar no se encontraron en el dataset: {invalid_cols}',
                        'detail': f'Las siguientes columnas a ignorar no se encontraron en el dataset: {invalid_cols}',
                        'error_code': 'INVALID_IGNORED_COLUMNS',
                        'error_type': 'validation_error',
                        'available_columns': list(df.columns),
                        'processed_ignored_columns': ignored_columns,
                        'raw_input': str(raw_ignored)
                    }, status=400)
            
            # 4. VALIDAR NOMBRES DUPLICADOS
            if is_public:
                # Para modelos públicos: verificar que no exista otro modelo público con el mismo nombre
                if AIModel.objects.filter(name=model_name, is_public=True).exists():
                    return Response({
                        'error': f'Ya existe un modelo público con el nombre "{model_name}"',
                        'detail': f'Ya existe un modelo público con el nombre "{model_name}"',
                        'error_code': 'DUPLICATE_PUBLIC_MODEL_NAME',
                        'error_type': 'validation_error'
                    }, status=400)
            else:
                # Para modelos privados: verificar que el usuario no tenga otro modelo privado con el mismo nombre
                if AIModel.objects.filter(user=request.user, name=model_name, is_public=False).exists():
                    return Response({
                        'error': f'Ya tienes un modelo privado con el nombre "{model_name}"',
                        'detail': f'Ya tienes un modelo privado con el nombre "{model_name}"',
                        'error_code': 'DUPLICATE_PRIVATE_MODEL_NAME',
                        'error_type': 'validation_error'
                    }, status=400)
            
            # 5. CREAR MODELO EN BD
            ai_model = AIModel.objects.create(
                user=request.user,
                name=model_name,
                task_type=task_type,
                target_column=target_column,
                dataset_name=csv_file.name,
                is_public=is_public,
                description=request.data.get('description', ''),
            )
            
            # 6. GUARDAR CSV TEMPORALMENTE
            csv_file.seek(0)
            
            # Crear directorio temporal para el usuario
            temp_dir = f"media/temp/{request.user.username}/"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Guardar archivo CSV con nombre único
            temp_csv_path = f"{temp_dir}{ai_model.id}.csv"
            with open(temp_csv_path, 'wb+') as destination:
                for chunk in csv_file.chunks():
                    destination.write(chunk)
            
            # 7. LANZAR ENTRENAMIENTO
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
                'status': 'pending',
                'debug_info': {
                    'raw_ignored_input': str(raw_ignored),
                    'processed_ignored_columns': ignored_columns,
                    'input_type': str(type(raw_ignored)),
                    'raw_is_public': str(raw_is_public),
                    'processed_is_public': is_public,
                    'is_public_type': str(type(raw_is_public))
                }
            }, status=201)
            
        except Exception as e:
            logging.error(f"CreateModelView error: {str(e)}", exc_info=True)
            
            # Manejar errores específicos de manera más amigable
            error_message = str(e)
            if 'pandas' in error_message.lower() or 'csv' in error_message.lower():
                return Response({
                    'error': 'Error al procesar el archivo CSV. Verifica que el formato sea correcto.',
                    'detail': f'Error al procesar el archivo CSV: {error_message}',
                    'error_code': 'CSV_PROCESSING_ERROR',
                    'error_type': 'validation_error'
                }, status=400)
            elif 'database' in error_message.lower() or 'integrity' in error_message.lower():
                return Response({
                    'error': 'Error de base de datos. Verifica que no exista un modelo con el mismo nombre.',
                    'detail': f'Error de base de datos: {error_message}',
                    'error_code': 'DATABASE_ERROR',
                    'error_type': 'database_error'
                }, status=400)
            else:
                return Response({
                    'error': 'Error interno del servidor. Por favor, intenta nuevamente.',
                    'detail': f'Error interno: {error_message}',
                    'error_code': 'INTERNAL_SERVER_ERROR',
                    'error_type': 'server_error'
                }, status=500)

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
            # Obtener configuración de paginación
            ml_settings = getattr(settings, 'ML_PLATFORM_SETTINGS', {})
            default_page_size = ml_settings.get('DEFAULT_PAGE_SIZE', 15)
            max_page_size = ml_settings.get('MAX_PAGE_SIZE', 100)
            
            # Obtener parámetros de paginación
            page = int(request.GET.get('page', 1))
            page_size = min(int(request.GET.get('page_size', default_page_size)), max_page_size)
            
            # Obtener todos los modelos del usuario autenticado ordenados por fecha
            models_queryset = AIModel.objects.filter(user=request.user).order_by('-created_at')
            
            # Aplicar paginación
            paginator = Paginator(models_queryset, page_size)
            
            # Validar que la página solicitada existe
            if page > paginator.num_pages:
                page = paginator.num_pages
            if page < 1:
                page = 1
                
            models_page = paginator.get_page(page)
            
            models_data = []
            for model in models_page:
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
                    'training_time': model.training_time,
                    'model_path': model.model_path if model.status == 'completed' else None
                })
            
            return Response({
                'count': paginator.count,  # Total de modelos
                'num_pages': paginator.num_pages,  # Total de páginas
                'current_page': page,  # Página actual
                'page_size': page_size,  # Tamaño de página
                'has_next': models_page.has_next(),  # Si hay página siguiente
                'has_previous': models_page.has_previous(),  # Si hay página anterior
                'next_page': page + 1 if models_page.has_next() else None,
                'previous_page': page - 1 if models_page.has_previous() else None,
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
            
            # Verificar que el archivo del modelo existe
            if not ai_model.model_path or not os.path.exists(ai_model.model_path):
                return Response({
                    'error': 'Model file not found',
                    'details': f'Model file does not exist: {ai_model.model_path}',
                    'suggestion': 'The model may have been deleted or corrupted. Please retrain the model.'
                }, status=404)
            
            # Obtener datos de entrada
            input_data = request.data.get('input_data', {})
            
            # Extraer nombres de features (manejar tanto strings como objetos)
            feature_names = []
            for feature in ai_model.features_list:
                if isinstance(feature, dict):
                    feature_names.append(feature.get('name', str(feature)))
                else:
                    feature_names.append(str(feature))
            
            # Validar que input_data no esté vacío
            if not input_data:
                return Response({
                    'error': 'Missing input_data in request body',
                    'required_structure': {
                        'input_data': {
                            feature: 'value' for feature in feature_names[:3]
                        }
                    },
                    'all_required_features': feature_names,
                    'note': 'Send a POST request with input_data containing all required features'
                }, status=400)
            
            # Validar que no todos los valores sean 0 o vacíos
            non_zero_values = []
            for key, value in input_data.items():
                if value is not None and value != 0 and value != '' and value != '0':
                    non_zero_values.append(key)
            
            if not non_zero_values:
                return Response({
                    'error': 'Invalid input data: all values are zero or empty',
                    'details': 'Please provide meaningful values for at least some features',
                    'received_data': input_data,
                    'suggestion': 'Enter realistic values for the features to get a meaningful prediction'
                }, status=400)
            
            # Nota: Las features faltantes son permitidas, PyCaret las manejará automáticamente
            # usando la media/moda calculada durante el entrenamiento
            missing_features = set(feature_names) - set(input_data.keys())
            if missing_features:
                logging.info(f"Missing features will be handled by PyCaret: {missing_features}")
                # Crear un DataFrame con todas las features, rellenando con None las faltantes
                complete_input_data = {}
                for feature_name in feature_names:
                    if feature_name in input_data:
                        complete_input_data[feature_name] = input_data[feature_name]
                    else:
                        complete_input_data[feature_name] = None  # PyCaret manejará esto
                input_data = complete_input_data
            
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
            import traceback
            logging.error(f"PredictView error: {str(e)}")
            logging.error(f"PredictView traceback: {traceback.format_exc()}")
            logging.error(f"PredictView input_data type: {type(input_data)}")
            logging.error(f"PredictView input_data content: {input_data}")
            return Response({'error': str(e)}, status=500)
    
    def _make_prediction(self, ai_model, input_data):
        """Hacer predicción usando el modelo guardado"""
        import pandas as pd
        import logging
        
        logging.info(f"_make_prediction input_data: {input_data}")
        logging.info(f"_make_prediction input_data type: {type(input_data)}")
        
        # Limpiar y validar input_data
        cleaned_input = {}
        for key, value in input_data.items():
            logging.info(f"Processing key: {key}, value: {value}, type: {type(value)}")
            # Si el valor es un diccionario, extraer solo el nombre
            if isinstance(value, dict):
                if 'name' in value:
                    cleaned_input[key] = value['name']
                else:
                    # Si no tiene 'name', convertir a string
                    cleaned_input[key] = str(value)
            elif isinstance(value, (list, tuple)):
                # Si es una lista o tupla, tomar el primer elemento o convertir a string
                cleaned_input[key] = value[0] if len(value) > 0 else str(value)
            else:
                # Para valores simples (string, int, float), mantener como están
                cleaned_input[key] = value
        
        logging.info(f"_make_prediction cleaned_input: {cleaned_input}")
        
        # Importar según tipo de tarea
        if ai_model.task_type == 'classification':
            from pycaret.classification import load_model as load_classification_model
            model = load_classification_model(ai_model.model_path.replace('.pkl', ''))
        else:
            from pycaret.regression import load_model as load_regression_model  
            model = load_regression_model(ai_model.model_path.replace('.pkl', ''))
        
        # Convertir input a DataFrame
        input_df = pd.DataFrame([cleaned_input])
        
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

class DeleteMultipleModelsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def __init__(self):
        super().__init__()
        # Obtener configuración de límites
        ml_settings = getattr(settings, 'ML_PLATFORM_SETTINGS', {})
        self.MAX_MODELS_PER_REQUEST = ml_settings.get('MAX_BULK_DELETE_MODELS', 100)
    
    def _delete_model_files(self, models_queryset):
        """Eliminar archivos físicos de modelos de forma segura"""
        files_deleted = 0
        files_failed = 0
        deleted_files = []
        failed_files = []
        
        for model in models_queryset:
            if model.model_path and os.path.exists(model.model_path):
                try:
                    os.remove(model.model_path)
                    files_deleted += 1
                    deleted_files.append({
                        'path': model.model_path,
                        'model_name': model.name,
                        'model_id': str(model.id)
                    })
                    logging.info(f"BULK_DELETE: Successfully deleted file: {model.model_path} for model {model.name}")
                except OSError as e:
                    files_failed += 1
                    failed_files.append({
                        'path': model.model_path,
                        'model_name': model.name,
                        'model_id': str(model.id),
                        'error': str(e)
                    })
                    logging.error(f"BULK_DELETE: Failed to delete file {model.model_path} for model {model.name}: {e}")
        
        return {
            'files_deleted': files_deleted,
            'files_failed': files_failed,
            'deleted_files': deleted_files,
            'failed_files': failed_files,
            'total_files': files_deleted + files_failed
        }

    def _bulk_delete_logic(self, request, method_used='DELETE'):
        """Lógica común para eliminación múltiple"""
        import time
        start_time = time.time()
        
        try:
            # Obtener array de IDs desde el body de la petición
            model_ids = request.data.get('model_ids', [])
            
            if not model_ids:
                return Response({
                    'error': 'model_ids array is required',
                    'error_code': 'BULK_001'
                }, status=400)
            
            if not isinstance(model_ids, list):
                return Response({
                    'error': 'model_ids must be an array',
                    'error_code': 'BULK_001'
                }, status=400)
            
            if len(model_ids) == 0:
                return Response({
                    'error': 'At least one model ID is required',
                    'error_code': 'BULK_001'
                }, status=400)
            
            # Verificar límites de operación masiva
            if len(model_ids) > self.MAX_MODELS_PER_REQUEST:
                return Response({
                    'error': f'Cannot delete more than {self.MAX_MODELS_PER_REQUEST} models at once',
                    'error_code': 'BULK_004',
                    'max_allowed': self.MAX_MODELS_PER_REQUEST
                }, status=400)
            
            if not isinstance(model_ids, list):
                return Response({'error': 'model_ids must be an array'}, status=400)
            
            if len(model_ids) == 0:
                return Response({'error': 'At least one model ID is required'}, status=400)
            
            # Obtener modelos que pertenecen al usuario
            models_to_delete = AIModel.objects.filter(
                id__in=model_ids, 
                user=request.user
            )
            
            # Verificar que todos los IDs pertenecen al usuario
            found_ids = set(str(model.id) for model in models_to_delete)
            requested_ids = set(str(id) for id in model_ids)
            not_found_ids = requested_ids - found_ids
            
            if not_found_ids:
                return Response({
                    'error': 'Some models not found or access denied',
                    'error_code': 'BULK_003',
                    'not_found_ids': list(not_found_ids),
                    'found_count': len(found_ids)
                }, status=404)
            
            # Recopilar nombres antes de eliminar
            deleted_models = []
            for model in models_to_delete:
                deleted_models.append({
                    'id': str(model.id),
                    'name': model.name
                })
            
            # IMPORTANTE: Eliminar archivos físicos ANTES de la eliminación en BD
            files_cleanup_result = self._delete_model_files(models_to_delete)
            
            # Eliminar todos los modelos de la base de datos
            deleted_count = models_to_delete.count()
            models_to_delete.delete()
            
            # Calcular duración de la operación
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log de auditoría con información de archivos
            logging.info(f"BULK_DELETE: User {request.user.username} ({request.user.id}) "
                        f"deleted {deleted_count} models using {method_used} method. "
                        f"Duration: {duration_ms}ms. Files deleted: {files_cleanup_result['files_deleted']}, "
                        f"Files failed: {files_cleanup_result['files_failed']}. "
                        f"Models: {[m['name'] for m in deleted_models]}")
            
            # Preparar respuesta con headers adicionales
            response_data = {
                'message': f'Successfully deleted {deleted_count} models',
                'deleted_count': deleted_count,
                'deleted_models': deleted_models,
                'method_used': method_used,
                'duration_ms': duration_ms,
                'files_cleanup': files_cleanup_result
            }
            
            response = Response(response_data)
            response['X-Delete-Method'] = method_used
            response['X-Bulk-Operation'] = 'true'
            response['X-Operation-Count'] = str(deleted_count)
            
            return response
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logging.error(f"BULK_DELETE ERROR: User {request.user.username} ({request.user.id}) "
                         f"failed bulk delete using {method_used}. Duration: {duration_ms}ms. Error: {str(e)}")
            return Response({
                'error': str(e),
                'error_code': 'BULK_005',
                'method_used': method_used
            }, status=500)
    
    def delete(self, request):
        """Método DELETE - Semánticamente correcto pero con limitaciones de compatibilidad"""
        return self._bulk_delete_logic(request, method_used='DELETE')
    
    def post(self, request):
        """Método POST - Fallback para máxima compatibilidad"""
        return self._bulk_delete_logic(request, method_used='POST')

class PublicModelsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Obtener configuración de paginación
            ml_settings = getattr(settings, 'ML_PLATFORM_SETTINGS', {})
            default_page_size = ml_settings.get('DEFAULT_PAGE_SIZE', 15)
            max_page_size = ml_settings.get('MAX_PAGE_SIZE', 100)
            
            # Obtener parámetros de paginación
            page = int(request.GET.get('page', 1))
            page_size = min(int(request.GET.get('page_size', default_page_size)), max_page_size)
            
            # Obtener todos los modelos públicos completados ordenados por fecha
            public_models_queryset = AIModel.objects.filter(
                is_public=True, 
                status='completed'
            ).order_by('-created_at')
            
            logging.info(f"Found {public_models_queryset.count()} public models")
            
            # Aplicar paginación
            paginator = Paginator(public_models_queryset, page_size)
            
            # Validar que la página solicitada existe
            if page > paginator.num_pages:
                page = paginator.num_pages
            if page < 1:
                page = 1
                
            models_page = paginator.get_page(page)
            
            models_data = []
            for model in models_page:
                try:
                    # Estadísticas generales del modelo
                    total_predictions = PredictionLog.objects.filter(ai_model=model).count()
                    unique_users = PredictionLog.objects.filter(ai_model=model).values('user').distinct().count()
                    
                    # Obtener métricas de forma segura
                    metrics = None
                    if hasattr(model, 'model_metrics') and model.model_metrics:
                        metrics = model.model_metrics
                    
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
                        'training_time': model.training_time,
                        'metrics': metrics,
                        'statistics': {
                            'total_predictions': total_predictions,
                            'unique_users': unique_users
                        }
                    })
                    
                except Exception as model_error:
                    logging.error(f"Error processing model {model.id}: {str(model_error)}")
                    continue
            
            logging.info(f"Successfully processed {len(models_data)} models")
            return Response({
                'count': paginator.count,  # Total de modelos públicos
                'num_pages': paginator.num_pages,  # Total de páginas
                'current_page': page,  # Página actual
                'page_size': page_size,  # Tamaño de página
                'has_next': models_page.has_next(),  # Si hay página siguiente
                'has_previous': models_page.has_previous(),  # Si hay página anterior
                'next_page': page + 1 if models_page.has_next() else None,
                'previous_page': page - 1 if models_page.has_previous() else None,
                'public_models': models_data
            })
            
        except Exception as e:
            logging.error(f"PublicModelsView error: {str(e)}")
            return Response({'error': str(e)}, status=500)

class QueueStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Obtener configuración de límites
            ml_settings = getattr(settings, 'ML_PLATFORM_SETTINGS', {})
            max_global_queue = ml_settings.get('MAX_GLOBAL_QUEUE_SIZE', 20)
            max_user_pending = ml_settings.get('MAX_USER_PENDING_MODELS', 3)
            
            user_plan = UserPlan.get_user_plan(request.user)
            
            # Información del plan del usuario
            plan_info = {
                'current_plan': user_plan.plan_type,
                'daily_model_limit': user_plan.daily_model_limit,
                'hourly_model_limit': user_plan.hourly_model_limit,
                'concurrent_model_limit': user_plan.concurrent_model_limit,
                'daily_prediction_limit': user_plan.daily_prediction_limit,
                'models_created_today': user_plan.get_daily_model_count(),
                'models_created_this_hour': user_plan.get_hourly_model_count(),
                'concurrent_models': user_plan.get_concurrent_model_count(),
                'predictions_today': user_plan.get_daily_prediction_count(),
                'can_create_model': user_plan.can_create_model()
            }
            
            # Estado de la cola global
            total_pending = AIModel.objects.filter(status='pending').count()
            total_training = AIModel.objects.filter(status='training').count()
            user_pending = AIModel.objects.filter(user=request.user, status='pending').count()
            
            queue_info = {
                'total_pending': total_pending,
                'total_training': total_training,
                'max_global_queue': max_global_queue,
                'queue_utilization_percent': round((total_pending / max_global_queue) * 100, 1) if max_global_queue > 0 else 0,
                'user_pending': user_pending,
                'max_user_pending': max_user_pending,
                'user_slots_available': max_user_pending - user_pending,
                'estimated_wait_time_minutes': total_pending * ml_settings.get('ESTIMATED_TRAINING_TIME_MINUTES', 30)
            }
            
            return Response({
                'plan_info': plan_info,
                'queue_info': queue_info,
                'timestamp': timezone.now()
            })
            
        except Exception as e:
            logging.error(f"QueueStatusView error: {str(e)}")
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

class SuggestTaskTypeView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # Validar que se envió un archivo CSV
            if 'file' not in request.FILES:
                return Response({
                    'error': 'Se requiere un archivo CSV para analizar',
                    'error_code': 'MISSING_CSV_FILE'
                }, status=400)
            
            csv_file = request.FILES['file']
            target_column = request.data.get('target_column')
            
            if not target_column:
                return Response({
                    'error': 'Se requiere especificar la columna objetivo',
                    'error_code': 'MISSING_TARGET_COLUMN'
                }, status=400)
            
            # Leer el archivo CSV
            try:
                df = pd.read_csv(csv_file)
                if df.empty:
                    return Response({
                        'error': 'El archivo CSV está vacío',
                        'error_code': 'EMPTY_CSV_FILE'
                    }, status=400)
            except Exception as e:
                return Response({
                    'error': f'Error al leer el archivo CSV: {str(e)}',
                    'error_code': 'INVALID_CSV_FILE'
                }, status=400)
            
            # Validar que la columna objetivo existe
            if target_column not in df.columns:
                return Response({
                    'error': f'La columna objetivo "{target_column}" no se encontró en el dataset',
                    'error_code': 'TARGET_COLUMN_NOT_FOUND',
                    'available_columns': list(df.columns)
                }, status=400)
            
            # Analizar la columna objetivo
            target_series = df[target_column].dropna()
            
            if len(target_series) == 0:
                return Response({
                    'error': 'La columna objetivo no tiene valores válidos',
                    'error_code': 'EMPTY_TARGET_COLUMN'
                }, status=400)
            
            # Lógica de sugerencia
            suggestion = self._analyze_target_column(target_series)
            
            # Información adicional del dataset
            dataset_info = {
                'total_rows': len(df),
                'total_columns': len(df.columns),
                'target_column_info': {
                    'name': target_column,
                    'non_null_values': len(target_series),
                    'unique_values': target_series.nunique(),
                    'data_type': str(target_series.dtype)
                }
            }
            
            return Response({
                'suggested_task_type': suggestion['task_type'],
                'confidence': suggestion['confidence'],
                'reasoning': suggestion['reasoning'],
                'dataset_info': dataset_info,
                'analysis_details': suggestion['details']
            })
            
        except Exception as e:
            logging.error(f"SuggestTaskTypeView error: {str(e)}", exc_info=True)
            return Response({
                'error': 'Error interno del servidor',
                'detail': str(e),
                'error_code': 'INTERNAL_SERVER_ERROR'
            }, status=500)
    
    def _analyze_target_column(self, target_series):
        """Analiza la columna objetivo y sugiere el tipo de tarea"""
        
        total_values = len(target_series)
        unique_values = target_series.nunique()
        data_type = target_series.dtype
        
        # Obtener algunos valores de ejemplo
        sample_values = target_series.unique()[:10].tolist()
        
        # Análisis por tipo de datos
        if pd.api.types.is_numeric_dtype(target_series):
            # Es numérico
            
            # Calcular ratio de valores únicos
            unique_ratio = unique_values / total_values
            
            # Verificar si son enteros
            is_integer = target_series.apply(lambda x: float(x).is_integer()).all()
            
            # Rango de valores
            min_val = target_series.min()
            max_val = target_series.max()
            
            if unique_values <= 20 and is_integer:
                # Pocos valores únicos enteros -> probablemente clasificación
                return {
                    'task_type': 'classification',
                    'confidence': 'alta',
                    'reasoning': f'La columna tiene {unique_values} valores únicos enteros, lo que sugiere categorías discretas.',
                    'details': {
                        'unique_values': unique_values,
                        'unique_ratio': round(unique_ratio, 3),
                        'is_integer': is_integer,
                        'sample_values': sample_values,
                        'range': f'{min_val} - {max_val}'
                    }
                }
            elif unique_ratio > 0.1:
                # Muchos valores únicos -> probablemente regresión
                return {
                    'task_type': 'regression',
                    'confidence': 'alta',
                    'reasoning': f'La columna tiene {unique_values} valores únicos ({round(unique_ratio*100, 1)}% del total), indicando valores continuos.',
                    'details': {
                        'unique_values': unique_values,
                        'unique_ratio': round(unique_ratio, 3),
                        'is_integer': is_integer,
                        'sample_values': sample_values,
                        'range': f'{min_val} - {max_val}'
                    }
                }
            else:
                # Caso ambiguo
                return {
                    'task_type': 'classification',
                    'confidence': 'media',
                    'reasoning': f'La columna tiene {unique_values} valores únicos. Podría ser clasificación con muchas clases o regresión con valores discretos.',
                    'details': {
                        'unique_values': unique_values,
                        'unique_ratio': round(unique_ratio, 3),
                        'is_integer': is_integer,
                        'sample_values': sample_values,
                        'range': f'{min_val} - {max_val}',
                        'note': 'Considera si los valores representan categorías o medidas continuas'
                    }
                }
        else:
            # No es numérico -> clasificación
            unique_ratio = unique_values / total_values
            
            if unique_values <= 50:
                confidence = 'alta'
                reasoning = f'La columna contiene texto/categorías con {unique_values} valores únicos, ideal para clasificación.'
            else:
                confidence = 'media'
                reasoning = f'La columna contiene texto con {unique_values} valores únicos. Muchas categorías pueden complicar la clasificación.'
            
            return {
                'task_type': 'classification',
                'confidence': confidence,
                'reasoning': reasoning,
                'details': {
                    'unique_values': unique_values,
                    'unique_ratio': round(unique_ratio, 3),
                    'data_type': str(data_type),
                    'sample_values': sample_values,
                    'note': 'Valores de texto indican clasificación' if unique_values <= 50 else 'Considera agrupar categorías similares'
                }
            }