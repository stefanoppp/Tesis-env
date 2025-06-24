from celery import shared_task
import pandas as pd
from .base_imports import *
from sklearn.impute import SimpleImputer
import numpy as np
from io import StringIO

@shared_task
def preprocesar_imputacion(df_serialized):
    try:
        logger.info("Iniciando imputación de valores faltantes")

        df = pd.read_json(StringIO(df_serialized), orient='split')
        logger.info(f"DataFrame shape: {df.shape}")

        # Trabajar con TODAS las columnas numéricas (incluidas categóricas)
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        
        if len(numeric_columns) == 0:
            logger.info("No hay columnas numéricas para imputar")
            return df.to_json(orient='split')

        df_imputed = df.copy()
        
        # Imputar valores faltantes con mediana (mejor para categóricas numéricas)
        imputer = SimpleImputer(strategy='median')
        df_imputed[numeric_columns] = imputer.fit_transform(df[numeric_columns])

        logger.info("Imputación completada")
        logger.info(f"Columnas procesadas: {numeric_columns.tolist()}")
        
        return df_imputed.to_json(orient='split')
        
    except Exception as e:
        logger.error(f"Error en imputación: {str(e)}")
        raise Exception("Error en imputación")