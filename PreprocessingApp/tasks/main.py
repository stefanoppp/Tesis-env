from celery import shared_task
from .base_imports import *
from PreprocessingApp.tasks.transformacion import preprocesar_transformacion
from PreprocessingApp.tasks.imputacion import preprocesar_imputacion
from PreprocessingApp.tasks.outliers import preprocesar_outliers
from PreprocessingApp.tasks.normalizacion import preprocesar_normalizacion
from celery import chain
from ..utils import get_user_directory_path
import pandas as pd
import os
from io import StringIO
import sys
@shared_task
def finalizar_procesamiento(df_json, csv_id):
    """Tarea final que guarda el archivo procesado"""
    try:
        logger.info(f"Finalizando procesamiento para CSV ID: {csv_id}")
        
        # Obtener el objeto CSV
        obj = CSVModel.objects.get(id=csv_id)
        
        # Crear directorio específico para este CSV: csv_uploads/username/csvname/
        user_directory = get_user_directory_path(obj.user)
        csv_filename = os.path.splitext(os.path.basename(obj.file.name))[0]  # Sin extensión
        project_directory = os.path.join(user_directory, csv_filename)
        os.makedirs(project_directory, exist_ok=True)
        
        # Convertir JSON a DataFrame
        df_final = pd.read_json(StringIO(df_json), orient='split')
        
        # Guardar archivo original en directorio del proyecto
        original_file_path = os.path.join(project_directory, f'original_{os.path.basename(obj.file.name)}')
        df_original = pd.read_csv(obj.file.path)
        df_original.to_csv(original_file_path, index=False)
        
        # Guardar archivo procesado (desde el JSON que viene de las tareas)
        processed_file_path = os.path.join(project_directory, f'processed_{os.path.basename(obj.file.name)}')
        df_final.to_csv(processed_file_path, index=False)
        
        # Actualizar modelo
        obj.processed_file.name = processed_file_path
        obj.is_ready = True
        obj.save()
        
        logger.info(f"Procesamiento completado para CSV ID: {csv_id}")
        return csv_id
        
    except Exception as e:
        logger.error(f"Error en finalización para CSV ID {csv_id}: {str(e)}")
        try:
            obj = CSVModel.objects.get(id=csv_id)
            obj.is_ready = False
            obj.error_message = str(e)  # <-- Linea agregada del testing
            obj.save()
        except Exception as inner_e:
            logger.error(f"Error guardando mensaje de error: {inner_e}")
        raise

@shared_task(bind=True)
def procesar_csv(self, csv_id):
    try:
        logger.info(f"Iniciando tarea principal para CSV ID: {csv_id}")
        
        # Crear cadena de tareas incluyendo la finalización
        task_chain = chain(
            preprocesar_transformacion.s(csv_id),
            preprocesar_imputacion.s(),
            preprocesar_outliers.s(),
            preprocesar_normalizacion.s(),
            finalizar_procesamiento.s(csv_id)  # Añadir CSV ID como parámetro
        )
        if 'test' in sys.argv:
            task_chain.apply()
        else:
            task_chain.apply_async()
        # Ejecutar cadena de forma asíncrona
        task_chain.apply_async()
        
        logger.info(f"Cadena de tareas iniciada para CSV ID: {csv_id}")
        return f"Procesamiento iniciado para CSV ID: {csv_id}"

    except Exception as e:
        logger.error(f"Error al iniciar procesamiento para CSV ID {csv_id}: {str(e)}")
        try:
            obj = CSVModel.objects.get(id=csv_id)
            obj.is_ready = False
            obj.error_message = str(e)
            obj.save()
        except Exception as inner_e:
            logger.error(f"Error guardando mensaje de error en procesar_csv: {inner_e}")
        return None