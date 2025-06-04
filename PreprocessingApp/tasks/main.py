from celery import shared_task
from .base_imports import *
from PreprocessingApp.tasks.transformacion import preprocesar_transformacion
from PreprocessingApp.tasks.imputacion import preprocesar_imputacion
from PreprocessingApp.tasks.outliers import preprocesar_outliers
from PreprocessingApp.tasks.normalizacion import preprocesar_normalizacion
from celery import chain
from ..utils import get_user_directory_path  # Importamos la función para manejar archivos

@shared_task(bind=True)
def procesar_csv(self, csv_id):
    try:
        logger.info(f"Iniciando tarea principal para CSV ID: {csv_id}")
        
        # Obtener el objeto CSV
        obj = CSVModel.objects.get(id=csv_id)
        
        # Crear la carpeta para el usuario donde se almacenarán los archivos
        user_directory = get_user_directory_path(obj.user)

        # Encadenar las tareas con link
        task_chain = chain(
            preprocesar_transformacion.s(csv_id),  # Primer tarea: transformación
            preprocesar_imputacion.s(),  # Segunda tarea: imputación
            preprocesar_outliers.s(),  # Tercera tarea: eliminación de outliers
            preprocesar_normalizacion.s(),  # Cuarta tarea: normalización
        )

        # Ejecutar las tareas en la cadena
        task_chain.apply_async()

        # Después de todo el procesamiento, guardamos el archivo procesado en la carpeta del usuario
        processed_file_path = os.path.join(user_directory, f'processed_{os.path.basename(obj.file.name)}')
        obj.processed_file.name = processed_file_path  # Almacenamos la nueva ruta en el modelo CSV
        
        obj.is_ready = True
        obj.save()

        logger.info(f"Estado de CSV ID: {csv_id} actualizado a 'is_ready=True' y archivo procesado guardado.")

        return csv_id  # Devuelve el ID del CSV si todo sale bien.

    except Exception as e:
        logger.error(f"Error en procesamiento para CSV ID {csv_id}: {str(e)}")
        return None
