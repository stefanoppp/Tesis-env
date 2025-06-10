from rest_framework import serializers
from .models import CSVModel

class CSVUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CSVModel
        fields = ['file']

    def validate_file(self, value):
        user = self.context['request'].user
        file_name = value.name
        if CSVModel.objects.filter(user=user, file__endswith=file_name).exists():
            raise serializers.ValidationError("Ya has subido un archivo con ese nombre.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        return CSVModel.objects.create(user=user, **validated_data)



class ProcessRequestSerializer(serializers.Serializer):
    csv_id = serializers.IntegerField()
    target_column = serializers.CharField(max_length=255)


class CSVResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CSVModel
        fields = [
            'id',
            'target_column',
            'processed_file',
            'is_ready',
            'error_message',
        ]
