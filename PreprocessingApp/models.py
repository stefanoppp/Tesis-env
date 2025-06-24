from django.db import models
from django.contrib.auth.models import User
import os
import shutil
from .utils.user_directory_utils import get_user_directory_path

def user_directory_path(instance, filename):
    """
    Función para generar una ruta personalizada para el archivo,
    almacenando los archivos CSV dentro de una carpeta por usuario.
    La ruta será csv_uploads/*username*/*csv_name*
    """
    # Obtener el nombre del archivo sin la extensión
    file_name = filename.split('.')[0]  # Nombre sin extensión
    user_folder_path = get_user_directory_path(instance.user)
    return os.path.join(user_folder_path, file_name, filename)

class CSVModel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='csvs')
    file = models.FileField(upload_to=user_directory_path)  # Archivo CSV original
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_file = models.FileField(upload_to=user_directory_path, blank=True, null=True)  # Archivo procesado
    is_ready = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)
    # --------------Datos para la siguiente aplicacion-------------
    processing_type = models.TextField(blank=True, null=True)
    target_column= models.TextField(blank=True, null=True) 
                    # Columna opcional a eliminar
    drop_column = models.TextField(blank=True, null=True)  
    original_filename = models.CharField(max_length=255, default='')
    def __str__(self):
        return f"CSV de {self.user.username} - {self.uploaded_at.date()}"

    def save(self, *args, **kwargs):
        """
        Sobrescribe el método save para configurar las rutas de archivo antes de guardar el modelo.
        """
        super().save(*args, **kwargs)
         # Guardar el modelo antes de hacer cualquier cambio adicional.
    def delete(self, *args, **kwargs):
        # Obtén la ruta absoluta de la carpeta del CSV usando el archivo existente
        if self.file and hasattr(self.file, 'path'):
            # Usar la carpeta donde está el archivo original
            user_folder = os.path.dirname(self.file.path)
            
            # Borra la carpeta principal y todo su contenido (incluye imgs/)
            if os.path.isdir(user_folder):
                shutil.rmtree(user_folder, ignore_errors=True)
        else:
            # Fallback: construir la ruta manualmente si no hay archivo
            if self.file and self.file.name:
                file_name = os.path.splitext(os.path.basename(self.file.name))[0]
                # Usar la misma lógica que user_directory_path
                user_folder_path = get_user_directory_path(self.user)
                user_folder = os.path.join(user_folder_path, file_name)
                
                if os.path.isdir(user_folder):
                    shutil.rmtree(user_folder, ignore_errors=True)

        super().delete(*args, **kwargs)