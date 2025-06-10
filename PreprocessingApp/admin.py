from django.contrib import admin
from .models import CSVModel

class CSVModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'file', 'uploaded_at', 'is_ready')
    list_filter = ('is_ready',)

    def delete_model(self, request, obj):
        obj.delete()  # Llama a tu método delete personalizado

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.delete()  # Llama a tu método delete personalizado para cada objeto

admin.site.register(CSVModel, CSVModelAdmin)