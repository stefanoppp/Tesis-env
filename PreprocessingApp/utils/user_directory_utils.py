import os
from django.contrib.auth.models import User

def get_user_directory_path(user: User):
    """
    Devuelve la ruta donde se guardarán los archivos CSV del usuario.
    Crea una carpeta personalizada para cada usuario dentro de 'csv_uploads/'.
    """
    user_folder_path = os.path.join('csv_uploads', user.username)
    # Asegurarse de que la carpeta del usuario exista
    os.makedirs(user_folder_path, exist_ok=True)
    return user_folder_path