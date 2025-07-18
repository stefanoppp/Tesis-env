from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.core.paginator import Paginator
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
                return Response({
                    'error': 'Se requiere un archivo CSV',
                    'detail': 'Se requiere un archivo CSV',
                    'error_code': 'MISSING_CSV_FILE',
                    'error_type': 'validation_error'
                }, status=400)
            
            csv_file = request.FILES['file']
            df = pd.read_csv(csv_file)
            
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
            
            # Parámetros adicionales
            raw_is_public = request.data.get('is_public', False)
            # Convertir string a boolean correctamente
            if isinstance(raw_is_public, str):
                is_public = raw_is_public.lower() in ['true', '1', 'yes']
            else:
                is_public = bool(raw_is_public)
            
            logging.info(f"Final ignored_columns: {ignored_columns}")
            logging.info(f"Raw is_public: {raw_is_public}, Processed is_public: {is_public}, Type: {type(raw_is_public)}")
            
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
                        'error': f'No puedes crear un modelo público con el nombre "{model_name}" porque ya existe otro modelo público con ese nombre en el repositorio global',
                        'detail': f'Ya existe un modelo público con el nombre "{model_name}" en el repositorio global. Los modelos públicos deben tener nombres únicos a nivel global.',
                        'error_code': 'DUPLICATE_PUBLIC_MODEL_NAME',
                        'error_type': 'validation_error'
                    }, status=400)
            else:
                # Para modelos privados: verificar que el usuario no tenga otro modelo privado con el mismo nombre
                if AIModel.objects.filter(user=request.user, name=model_name, is_public=False).exists():
                    return Response({
                        'error': f'No puedes crear un modelo privado con el nombre "{model_name}" porque ya tienes otro modelo privado con ese nombre en tu colección personal',
                        'detail': f'Ya tienes un modelo privado con el nombre "{model_name}" en tu colección personal. Cada modelo privado debe tener un nombre único dentro de tu colección.',
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
            logging.error(f"CreateModelView error: {str(e)}")
            return Response({
                'error': f'Error interno del servidor: {str(e)}',
                'detail': f'Error interno del servidor: {str(e)}',
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
            # Obtener parámetros de paginación
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 15))
            
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
            
            # Validar features faltantes
            missing_features = set(feature_names) - set(input_data.keys())
            if missing_features:
                # Crear ejemplo con valores placeholder
                example_data = {}
                for feature_name in feature_names:
                    if feature_name in input_data:
                        example_data[feature_name] = input_data[feature_name]  # Mantener valores existentes
                    else:
                        # Sugerir valores de ejemplo según el nombre
                        if any(word in feature_name.lower() for word in ['type', 'class', 'category']):
                            example_data[feature_name] = 'example_category'
                        elif any(word in feature_name.lower() for word in ['name', 'id']):
                            example_data[feature_name] = 'example_name'
                        elif any(word in feature_name.lower() for word in ['generation', 'year', 'age']):
                            example_data[feature_name] = 1
                        else:
                            example_data[feature_name] = 100  # Valor numérico por defecto
                
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
                        f'4. This model needs {len(feature_names)} features total'
                    ],
                    'all_required_features': feature_names
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
    
    # Límites de operaciones masivas
    MAX_MODELS_PER_REQUEST = 100
    
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
            # Obtener parámetros de paginación
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 15))
            
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