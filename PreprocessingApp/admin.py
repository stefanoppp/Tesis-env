from django.contrib import admin
from .models import CSVModel

@admin.register(CSVModel)
class CSVModelAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'uploaded_at', 'target_column', 'is_ready']
    list_filter = ['is_ready', 'uploaded_at']
    search_fields = ['user__username', 'target_column']

