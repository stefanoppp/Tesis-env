from rest_framework import serializers
from .models import CSVModel

class CSVUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CSVModel
        fields = ['file']

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
            'report_image_outliers',
            'report_image_distribution',
            'report_image_missing',
            'is_ready',
            'error_message',
        ]
