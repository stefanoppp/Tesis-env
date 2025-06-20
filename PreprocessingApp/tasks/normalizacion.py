from celery import shared_task
from .base_imports import *
from io import StringIO

@shared_task
def preprocesar_normalizacion(df_serialized):
    try:
        logger.info(f"Iniciando normalización de datos")

        # Convertir el DataFrame serializado de nuevo a DataFrame
        df = pd.read_json(StringIO(df_serialized), orient='split')

        # Normalización de los datos: escalar los valores
        df_normalized = df.copy()
        numeric_columns = df_normalized.select_dtypes(include=['float64', 'int64']).columns
        df_normalized[numeric_columns] = StandardScaler().fit_transform(df_normalized[numeric_columns])

        # Registrar las columnas y el tamaño después de la normalización
        logger.info(f"Normalización completada con éxito")

        # Devolver el DataFrame normalizado
        df_normalized.to_json(orient='split')  # Devuelve el DataFrame normalizado en formato JSON
        return df_normalized.to_json(orient='split')
    except Exception as e:
        logger.error(f"Error en normalización de datos: {str(e)}")
        raise Exception("Error en normalización de datos")

