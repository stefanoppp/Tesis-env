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

        file_name = file.name.split('/')[-1]
        user_folder = os.path.join('csv_uploads', request.user.username, file_name.split('.')[0])
        file_path = os.path.join(user_folder, file_name)
        processing_type= request.data.get('processing_type')
        target_column = request.data.get('target_column')
        print(processing_type, target_column)
        if not processing_type:
            return Response({'error': 'Debe proporcionar algún tipo de procesamiento'}, status=400)
        
        if not target_column:
            return Response({'error': 'Debe proporcionar la columna objetivo'}, status=400)
        try:
            df = pd.read_csv(file)
        except Exception:
            return Response({'error': 'El archivo no es un CSV válido.'}, status=400)

        if target_column not in df.columns:
            return Response({'error': f'La columna objetivo "{target_column}" no existe en el archivo.'}, status=400)

        # Verifica en la base de datos
        if CSVModel.objects.filter(user=request.user, file__endswith=file_name).exists():
            return Response({'error': 'Ya subiste este archivo antes'}, status=400)

        # Verifica en el sistema de archivos
        if os.path.exists(file_path):
            return Response({'error': 'Ya existe un archivo físico con ese nombre. Eliminalo antes de volver a subir.'}, status=400)

        # Guardar el archivo en el modelo
        csv_instance = CSVModel.objects.create(user=request.user, file=file, target_column=target_column, processing_type=processing_type)

        # Llamar a Celery para procesar el archivo
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

