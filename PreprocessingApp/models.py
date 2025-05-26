from django.db import models
from django.contrib.auth.models import User

class CSVModel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='csvs')
    file = models.FileField(upload_to='csv_uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    target_column = models.CharField(max_length=255, blank=True, null=True)

    processed_file = models.FileField(upload_to='csv_processed/', blank=True, null=True)
    report_image_outliers = models.TextField(blank=True, null=True)  # base64
    report_image_distribution = models.TextField(blank=True, null=True)
    report_image_missing = models.TextField(blank=True, null=True)

    is_ready = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True) 

    def __str__(self):
        return f"CSV de {self.user.username} - {self.uploaded_at.date()}"

