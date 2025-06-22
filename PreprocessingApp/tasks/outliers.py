import numpy as np
from celery import shared_task
from .base_imports import *
from io import StringIO
from scipy import stats

@shared_task
def preprocesar_outliers(df_serialized):
    try:
        logger.info(f"Iniciando eliminación de outliers (IQR)")
        df = pd.read_json(StringIO(df_serialized), orient='split')
        df_num = df.select_dtypes(include=[np.number])
        if df_num.shape[1] == 0:
            logger.info("No hay columnas numéricas para eliminar outliers.")
            return df.to_json(orient='split')
        mask = np.ones(len(df), dtype=bool)
        for col in df_num.columns:
            q1 = df[col].quantile(0.15)
            q3 = df[col].quantile(0.85)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            mask &= (df[col] >= lower) & (df[col] <= upper)
        df_cleaned = df[mask]
        logger.info(f"Filas antes: {len(df)}, después de IQR: {len(df_cleaned)}")
        return df_cleaned.to_json(orient='split')
    except Exception as e:
        logger.error(f"Error en eliminación de outliers: {str(e)}")
        raise Exception("Error en eliminación de outliers")