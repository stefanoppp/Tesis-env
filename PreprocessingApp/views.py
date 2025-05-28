from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from PreprocessingApp.tasks import procesar_csv

from .models import CSVModel
from .serializers import CSVUploadSerializer, ProcessRequestSerializer, CSVResultSerializer
from .tasks import procesar_csv

class UploadCSVView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file = request.FILES.get('csv')
        if not file:
            return Response({'error': 'No se proporcionó ningún archivo CSV'}, status=400)

        file_name = file.name.split('/')[-1]  # Asegura que solo se use el nombre sin el path
        if CSVModel.objects.filter(user=request.user, file__icontains=file_name).exists():
            return Response({'error': 'Ya subiste este archivo antes'}, status=400)

        # Guardar archivo
        csv_instance = CSVModel.objects.create(user=request.user, file=file.name)
        procesar_csv.delay(csv_instance.id)

        return Response({'message': 'Archivo subido y procesamiento iniciado'}, status=201)


class LaunchProcessingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ProcessRequestSerializer(data=request.data)
        if serializer.is_valid():
            csv_id = serializer.validated_data['csv_id']
            target_column = serializer.validated_data['target_column']

            try:
                obj = CSVModel.objects.get(id=csv_id, user=request.user)
                obj.target_column = target_column
                obj.is_ready = False
                obj.save()

                procesar_csv.delay(obj.id)
                return Response({'message': 'Preprocesamiento lanzado'}, status=200)
            except CSVModel.DoesNotExist:
                return Response({'error': 'CSV no encontrado'}, status=404)
        return Response(serializer.errors, status=400)


class GetResultsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        csv_id = request.query_params.get('csv_id')
        try:
            obj = CSVModel.objects.get(id=csv_id, user=request.user)
            if not obj.is_ready:
                return Response({'message': 'Aún procesando...'}, status=202)

            serializer = CSVResultSerializer(obj)
            return Response(serializer.data, status=200)
        except CSVModel.DoesNotExist:
            return Response({'error': 'CSV no encontrado'}, status=404)
