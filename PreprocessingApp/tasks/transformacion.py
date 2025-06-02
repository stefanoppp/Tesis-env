from celery import shared_task
from .base_imports import *
import pandas as pd

@shared_task
def preprocesar_transformacion(csv_id):
    try:
        logger.info(f"Iniciando transformación de valores para CSV ID: {csv_id}")

        # Obtener el CSV
        obj = CSVModel.objects.get(id=csv_id)
        df = pd.read_csv(obj.file.path)

        # Eliminar columnas no numéricas
        df = df.select_dtypes(include=['number'])

        # Transformación de valores: convertir fechas, texto a números, etc.
        df = df.apply(pd.to_numeric, errors='coerce')  # Convertir todo a numérico donde sea posible

        # Convertir el DataFrame a un formato serializable (por ejemplo, JSON)
        df_serialized = df.to_json(orient='split')

        logger.info(f"Transformación de valores completada para CSV ID: {csv_id}")
        return df_serialized  # Devuelve el DataFrame serializado

    except Exception as e:
        logger.error(f"Error en transformación de valores para CSV ID {csv_id}: {str(e)}")
        raise Exception(f"Error en transformación de valores para CSV ID {csv_id}")
