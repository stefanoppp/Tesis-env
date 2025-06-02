from celery import shared_task
from .base_imports import *
from PreprocessingApp.tasks.transformacion import preprocesar_transformacion
from PreprocessingApp.tasks.imputacion import preprocesar_imputacion

@shared_task(bind=True)
def procesar_csv(self, csv_id):
    try:
        logger.info(f"Iniciando tarea principal para CSV ID: {csv_id}")

        # Llamar a la tarea de transformación y encadenar la tarea de imputación
        preprocesar_transformacion.apply_async(args=[csv_id], link=preprocesar_imputacion.s())

        return csv_id  # Devuelve el ID del CSV si todo sale bien.

    except Exception as e:
        logger.error(f"Error en procesamiento para CSV ID {csv_id}: {str(e)}")
        return None
