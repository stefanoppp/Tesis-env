# PreprocessingApp/tasks/graficos.py
from celery import shared_task
from PreprocessingApp.models import CSVModel
import pandas as pd
import logging
from PreprocessingApp.preprocessing_utils import PreProcessor

logger = logging.getLogger(__name__)

@shared_task
def preprocesar_codigo_base64(csv_id, df_serialized):
    try:
        logger.info(f"Iniciando generación de gráficos para CSV ID: {csv_id}")
        
        df = pd.DataFrame(df_serialized)

        # Aquí iría el código para la generación de gráficos, similar a tu implementación anterior.
        processor = PreProcessor(df)
        col = df.columns[0]  # Usamos la primera columna por ahora

        outliers_img = processor.plot_comparative(df, df, col, 'outliers')
        dist_img = processor.plot_comparative(df, df, col, 'distributions')
        missing_img = processor.plot_missing_values(df, df)

        processor.save_images(outliers_img, dist_img, missing_img)

        logger.info(f"Generación de gráficos completada para CSV ID: {csv_id}")
        return {"status": "Generación de gráficos completada", "csv_id": csv_id}

    except Exception as e:
        logger.error(f"Error en generación de gráficos para CSV ID {csv_id}: {str(e)}")
        raise Exception(f"Error en generación de gráficos para CSV ID {csv_id}")

