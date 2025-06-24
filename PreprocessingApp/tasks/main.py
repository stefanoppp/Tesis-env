from celery import shared_task
from .base_imports import *
from PreprocessingApp.tasks.transformacion import preprocesar_transformacion
from PreprocessingApp.tasks.imputacion import preprocesar_imputacion
from PreprocessingApp.tasks.outliers import preprocesar_outliers
from PreprocessingApp.tasks.normalizacion import preprocesar_normalizacion
from PreprocessingApp.tasks.registros_duplicados import preprocesar_duplicados
from celery import chain
from PreprocessingApp.models import CSVModel
import pandas as pd
import os
from io import StringIO
import sys

@shared_task
def finalizar_procesamiento(df_json, csv_id):
    """Tarea final que guarda el archivo procesado en la misma carpeta que el original"""
    try:
        logger.info(f"Finalizando procesamiento para CSV ID: {csv_id}")
        obj = CSVModel.objects.get(id=csv_id)
        # Usar la misma carpeta donde está el csv_original.csv
        project_directory = os.path.dirname(obj.file.path)
        os.makedirs(project_directory, exist_ok=True)
        df_final = pd.read_json(StringIO(df_json), orient='split')
        processed_file_path = os.path.join(project_directory, 'csv_procesado.csv')
        df_final.to_csv(processed_file_path, index=False)
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
            obj.error_message = str(e)
            obj.save()
        except Exception as inner_e:
            logger.error(f"Error guardando mensaje de error: {inner_e}")
        raise

@shared_task(bind=True)
def procesar_csv(self, csv_id, drop_column=None):
    try:
        logger.info(f"Iniciando tarea principal para CSV ID: {csv_id}")
        obj = CSVModel.objects.get(id=csv_id)
        
        # Cargar el DataFrame original
        df = pd.read_csv(obj.file.path)
        
        # Eliminar columnas si corresponde
        if drop_column and drop_column in df.columns:
            logger.info(f"Eliminando columna {drop_column} del DataFrame")
            df = df.drop(columns=[drop_column])
        
        # Obtener target_column del modelo
        target_column = obj.target_column
        
        # Convertir el DataFrame a JSON
        df_json = df.to_json(orient='split')

        # Crear cadena de tareas PASANDO target_column desde el primer paso
        task_chain = chain(
            preprocesar_transformacion.s(df_json, csv_id, target_column),  # ← AGREGAR target_column
            preprocesar_duplicados.s(),
            preprocesar_imputacion.s(),
            preprocesar_outliers.s(),
            preprocesar_normalizacion.s(target_column),
            finalizar_procesamiento.s(csv_id)
        )

        if 'test' in sys.argv:
            task_chain.apply()
        else:
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
            logger.error(f"Error guardando mensaje de error: {inner_e}")
        return None