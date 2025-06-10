from django.db import models
from django.contrib.auth.models import User
import os
import shutil

def user_directory_path(instance, filename):
    """
    Función para generar una ruta personalizada para el archivo,
    almacenando los archivos CSV dentro de una carpeta por usuario.
    La ruta será csv_uploads/*username*/*csv_name*
    """
    # Obtener el nombre del archivo sin la extensión
    file_name = filename.split('.')[0]  # Nombre sin extensión
    user_folder_path = os.path.join('csv_uploads', instance.user.username, file_name)
    
    # Asegurarse de que la carpeta exista (esto se maneja en el save())
    return os.path.join(user_folder_path, filename)

class CSVModel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='csvs')
    file = models.FileField(upload_to=user_directory_path)  # Archivo CSV original
    uploaded_at = models.DateTimeField(auto_now_add=True)

    processed_file = models.FileField(upload_to=user_directory_path, blank=True, null=True)  # Archivo procesado

    is_ready = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"CSV de {self.user.username} - {self.uploaded_at.date()}"

    def save(self, *args, **kwargs):
        """
        Sobrescribe el método save para configurar las rutas de archivo antes de guardar el modelo.
        """
        super().save(*args, **kwargs)  # Guardar el modelo antes de hacer cualquier cambio adicional.
    def delete(self, *args, **kwargs):
        # Obtén la ruta de la carpeta del CSV
        file_name = os.path.splitext(os.path.basename(self.file.name))[0]
        user_folder = os.path.join('csv_uploads', self.user.username, file_name)
        # Borra la carpeta y todo su contenido si existe
        if os.path.isdir(user_folder):
            shutil.rmtree(user_folder, ignore_errors=True)
        # Borra los archivos individuales si por alguna razón están fuera de la carpeta
        if self.file and os.path.exists(self.file.path):
            try:
                os.remove(self.file.path)
            except Exception:
                pass
        if self.processed_file and self.processed_file.name and os.path.exists(self.processed_file.path):
            try:
                os.remove(self.processed_file.path)
            except Exception:
                pass
        super().delete(*args, **kwargs)