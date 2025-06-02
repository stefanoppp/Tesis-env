from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import CSVModel
from .serializers import CSVUploadSerializer, ProcessRequestSerializer, CSVResultSerializer
from .tasks.main import procesar_csv

class UploadCSVView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file = request.FILES.get('csv')
        if not file:
            return Response({'error': 'No se proporcionó ningún archivo CSV'}, status=400)

        file_name = file.name.split('/')[-1]
        
        if CSVModel.objects.filter(user=request.user, file__icontains=file_name).exists():
            return Response({'error': 'Ya subiste este archivo antes'}, status=400)

        # Guardar el archivo en el modelo
        csv_instance = CSVModel.objects.create(user=request.user, file=file)

        # Llamar a Celery para procesar el archivo
        task = procesar_csv.apply_async(args=[csv_instance.id])

        # Retornar el id para que el frontend pueda usarlo en futuras consultas
        return Response({
            'message': 'Archivo subido y procesamiento iniciado',
            'csv_id': csv_instance.id,  # Devolvemos el ID del CSV
            'task_id': task.id  # Devolvemos el ID de la tarea en caso de querer consultar su estado
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


class GetResultsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        csv_id = request.query_params.get('csv_id')
        try:
            obj = CSVModel.objects.get(id=csv_id, user=request.user)
            if obj.status == 'processing' or obj.status == 'pending':
                return Response({'message': 'Aún procesando...'}, status=202)

            serializer = CSVResultSerializer(obj)
            return Response(serializer.data, status=200)
        except CSVModel.DoesNotExist:
            return Response({'error': 'CSV no encontrado'}, status=404)

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
                        'processed_file_url': request.build_absolute_uri(csv_obj.processed_file.url),
                        'report_image_outliers': csv_obj.report_image_outliers,
                        'report_image_distribution': csv_obj.report_image_distribution,
                        'report_image_missing': csv_obj.report_image_missing,
                    })

            return Response(response_data)

        except CSVModel.DoesNotExist:
            return Response({'error': 'CSV no encontrado o no pertenece al usuario.'}, status=status.HTTP_404_NOT_FOUND)

