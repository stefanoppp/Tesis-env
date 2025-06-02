from celery import shared_task
from .base_imports import *

@shared_task
def preprocesar_outliers(csv_id, df_serialized):
    try:
        logger.info(f"Iniciando eliminación de outliers para CSV ID: {csv_id}")
        
        df = pd.DataFrame(df_serialized)

        # Eliminar outliers
        z_scores = stats.zscore(df.select_dtypes(include=['float64', 'int64']))
        df_cleaned = df[(abs(z_scores) < 3).all(axis=1)]  # Filtra los outliers

        logger.info(f"Eliminación de outliers completada para CSV ID: {csv_id}")

        return df_cleaned.to_dict()  # Pasar el resultado a la siguiente tarea

    except Exception as e:
        logger.error(f"Error en eliminación de outliers para CSV ID {csv_id}: {str(e)}")
        raise Exception(f"Error en eliminación de outliers para CSV ID {csv_id}")

