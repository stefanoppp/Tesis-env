from celery import shared_task
from .base_imports import *
from io import StringIO

@shared_task
def preprocesar_outliers(df_serialized):
    try:
        logger.info(f"Iniciando eliminación de outliers")

        # Convertir el DataFrame serializado de nuevo a DataFrame
        df = pd.read_json(StringIO(df_serialized), orient='split')

        # Calcular Z-score para encontrar outliers
        z_scores = stats.zscore(df.select_dtypes(include=['float64', 'int64']))
        df_cleaned = df[(abs(z_scores) < 3).all(axis=1)]  # Eliminar outliers (valores con z-score > 3)

        # Registrar las columnas y el tamaño después de la eliminación de outliers
        logger.info(f"Eliminacón de outliers completada con éxito")

        # Devolver el DataFrame limpio después de eliminar los outliers
        return df_cleaned.to_json(orient='split')  # Devuelve el DataFrame limpio en formato JSON

    except Exception as e:
        logger.error(f"Error en eliminación de outliers: {str(e)}")
        raise Exception("Error en eliminación de outliers")


