from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status

from .models import CSVModel
from .serializers import CSVUploadSerializer, ProcessRequestSerializer, CSVResultSerializer
from .tasks import procesar_csv

class UploadCSVView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        serializer = CSVUploadSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            instance = serializer.save()
            return Response({'message': 'Archivo subido correctamente', 'id': instance.id}, status=201)
        return Response(serializer.errors, status=400)


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
