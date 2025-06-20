from celery import shared_task
from .base_imports import *
import pandas as pd
from io import StringIO

@shared_task
def preprocesar_transformacion(df_json, csv_id):
    try:
        logger.info(f"Iniciando transformación de valores para CSV ID: {csv_id}")

        # Usar el DataFrame recibido, NO volver a leer el archivo original
        df = pd.read_json(StringIO(df_json), orient='split')

        # Eliminar columnas no numéricas
        df = df.select_dtypes(include=['number'])

        # Transformación de valores: convertir fechas, texto a números, etc.
        df = df.apply(pd.to_numeric, errors='coerce')  # Convertir todo a numérico donde sea posible

        # Convertir el DataFrame a un formato serializable JSON
        df_serialized = df.to_json(orient='split')

        logger.info(f"Transformación de valores completada para CSV ID: {csv_id}")
        return df_serialized

    except Exception as e:
        logger.error(f"Error en transformación de valores para CSV ID {csv_id}: {str(e)}")
        raise Exception(f"Error en transformación de valores para CSV ID {csv_id}")