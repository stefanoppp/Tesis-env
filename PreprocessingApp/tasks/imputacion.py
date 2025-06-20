from celery import shared_task
import pandas as pd
from .base_imports import *
from sklearn.impute import SimpleImputer

import pandas as pd
from io import StringIO

@shared_task
def preprocesar_imputacion(df_serialized):
    try:
        logger.info(f"Iniciando imputación de valores faltantes")

        # Convertir el string JSON en un objeto 'archivo' para evitar el FutureWarning
        df = pd.read_json(StringIO(df_serialized), orient='split')

        # Imputación de valores faltantes
        numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns
        df_clean = df[numeric_columns]

        imputer = SimpleImputer(strategy='mean')
        df_imputed = df_clean.copy()
        
        # Aplicar la imputación y reemplazar en el DataFrame original
        df_imputed[numeric_columns] = imputer.fit_transform(df_clean)

        logger.info(f"Imputación completada para CSV")
        logger.info(f"Columnas resultantes después de imputación: {df_imputed.columns.tolist()}")
        df_serialized = df_imputed.to_json(orient='split')
        return df_serialized
    except Exception as e:
        logger.error(f"Error en imputación: {str(e)}")
        raise Exception("Error en imputación")
