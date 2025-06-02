from celery import shared_task
from .base_imports import *

@shared_task
def preprocesar_normalizacion(csv_id, df_serialized):
    try:
        logger.info(f"Iniciando normalización para CSV ID: {csv_id}")
        
        df = pd.DataFrame(df_serialized)

        # Normalización de los datos
        df[df.select_dtypes(include=['float64', 'int64']).columns] = StandardScaler().fit_transform(df[df.select_dtypes(include=['float64', 'int64']).columns])

        logger.info(f"Normalización completada para CSV ID: {csv_id}")

        return df.to_dict()  # Pasar el resultado a la siguiente tarea

    except Exception as e:
        logger.error(f"Error en normalización para CSV ID {csv_id}: {str(e)}")
        raise Exception(f"Error en normalización para CSV ID {csv_id}")
