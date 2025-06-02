from django.contrib import admin
from .models import CSVModel

class CSVModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'file', 'uploaded_at', 'is_ready')  # Elimina 'target_column' y 'status'
    list_filter = ('is_ready',)  # Elimina 'status'

admin.site.register(CSVModel, CSVModelAdmin)
