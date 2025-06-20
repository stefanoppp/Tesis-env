import os
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import pandas as pd
from .models import CSVModel
from .serializers import CSVUploadSerializer, ProcessRequestSerializer, CSVResultSerializer
from .tasks.main import procesar_csv
from django.conf import settings
import os

class UploadCSVView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file = request.FILES.get('csv')
        if not file:
            return Response({'error': 'No se proporcionó ningún archivo CSV'}, status=400)

        # Validar extensión
        if not file.name.lower().endswith('.csv'):
            return Response({'error': 'El archivo debe ser un CSV'}, status=400)

        # Carpeta: csv_uploads/<user>/<csv_name>/
        csv_name = os.path.splitext(file.name)[0]
        user_folder = os.path.join('csv_uploads', request.user.username, csv_name)
        os.makedirs(user_folder, exist_ok=True)
        file_path = os.path.join(user_folder, 'csv_original.csv')

        processing_type = request.data.get('processing_type')
        target_column = request.data.get('target_column')
        drop_columns = request.data.get('drop_columns')  # Puede ser None, string o lista

        if not processing_type:
            return Response({'error': 'Debe proporcionar algún tipo de procesamiento'}, status=400)
        if not target_column:
            return Response({'error': 'Debe proporcionar la columna objetivo'}, status=400)

        # Leer el archivo para validar el target y eliminar columnas si corresponde
        try:
            df = pd.read_csv(file)
        except Exception:
            return Response({'error': 'El archivo no es un CSV válido.'}, status=400)

        if target_column not in df.columns:
            return Response({'error': f'La columna objetivo "{target_column}" no existe en el archivo.'}, status=400)

        # Normaliza drop_columns a lista
        if drop_columns is None:
            drop_columns_list = []
        elif isinstance(drop_columns, str):
            drop_columns_list = [col.strip() for col in drop_columns.split(',') if col.strip()]
        elif isinstance(drop_columns, list):
            drop_columns_list = drop_columns
        else:
            return Response({'error': 'El parámetro drop_columns debe ser una lista o una cadena separada por comas.'}, status=400)

        # Eliminar las columnas si existen
        not_found = [col for col in drop_columns_list if col not in df.columns]
        if not_found:
            return Response({'error': f'Las columnas a suprimir no existen en el archivo: {not_found}'}, status=400)
        if drop_columns_list:
            df = df.drop(columns=drop_columns_list)

        # Verifica si el usuario ya subió un archivo con el mismo nombre original
        if CSVModel.objects.filter(user=request.user, original_filename=file.name).exists():
            return Response({'error': 'Ya subiste un archivo con ese nombre antes'}, status=400)

        # Guarda el DataFrame (ya recortado si corresponde) en el sistema de archivos
        df.to_csv(file_path, index=False)

        # Crea el modelo CSVModel
        csv_instance = CSVModel.objects.create(
            user=request.user,
            file=file_path,
            target_column=target_column,
            processing_type=processing_type,
            drop_column=",".join(drop_columns_list) if drop_columns_list else None,
            original_filename=file.name,
        )

        # Lanza la tarea de preprocesamiento SOLO con el id
        task = procesar_csv.apply_async(args=[csv_instance.id])

        return Response({
            'message': 'Archivo subido y procesamiento iniciado',
            'csv_id': csv_instance.id,
            'task_id': task.id
        }, status=201)
class LaunchProcessingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ProcessRequestSerializer(data=request.data)
        if serializer.is_valid():
            csv_id = serializer.validated_data['csv_id']

            try:
                obj = CSVModel.objects.get(id=csv_id, user=request.user)
                obj.is_ready = False
                obj.save()

                procesar_csv.delay(obj.id)
                return Response({'message': 'Preprocesamiento lanzado', "id": csv_id}, status=200)
            except CSVModel.DoesNotExist:
                return Response({'error': 'CSV no encontrado'}, status=404)
        return Response(serializer.errors, status=400)

class MyCSVListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        csvs = CSVModel.objects.filter(user=request.user)
        data = [
            {
                "id": csv.id,
                "file_name": csv.file.name.split('/')[-1]
            }
            for csv in csvs
        ]
        return Response(data)

class CSVStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, csv_id):
        try:
            # Obtener el objeto CSV
            csv_obj = CSVModel.objects.get(id=csv_id, user=request.user)

            # Verificar el estado del preprocesamiento
            response_data = {
                'is_ready': csv_obj.is_ready,
            }

            # Si el preprocesamiento está listo, devolver los resultados
            if csv_obj.is_ready:
                if csv_obj.error_message:
                    response_data['error'] = csv_obj.error_message
                else:
                    response_data.update({
                        'processed_file_url': request.build_absolute_uri(csv_obj.processed_file.url)
                    })

            return Response(response_data)

        except CSVModel.DoesNotExist:
            return Response({'error': 'CSV no encontrado o no pertenece al usuario.'}, status=status.HTTP_404_NOT_FOUND)

