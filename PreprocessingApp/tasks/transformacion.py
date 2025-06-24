from celery import shared_task
from .base_imports import *
from io import StringIO
import numpy as np

@shared_task
def preprocesar_transformacion(df_json, csv_id, target_column=None):
    try:
        logger.info(f"Iniciando transformación de valores para CSV ID: {csv_id}")
        logger.info(f"Target column: {target_column}")

        df = pd.read_json(StringIO(df_json), orient='split')
        logger.info(f"DataFrame shape inicial: {df.shape}")
        logger.info(f"Columnas iniciales: {df.columns.tolist()}")
        
        # Conservar TODAS las columnas numéricas (incluidas las categóricas)
        df_numerico = df.select_dtypes(include=['number']).copy()
        
        # Intentar convertir columnas no numéricas a numéricas si es posible
        columnas_convertidas = []
        for col in df.columns:
            if col not in df_numerico.columns:
                try:
                    df_convertida = pd.to_numeric(df[col], errors='coerce')
                    # Solo agregar si la conversión fue exitosa (no todo NaN)
                    if not df_convertida.isnull().all():
                        df_numerico[col] = df_convertida
                        columnas_convertidas.append(col)
                except:
                    continue
        
        if columnas_convertidas:
            logger.info(f"Columnas convertidas a numéricas: {columnas_convertidas}")
        
        logger.info(f"Columnas finales conservadas: {df_numerico.columns.tolist()}")
        logger.info(f"Shape final: {df_numerico.shape}")
        logger.info(f"Transformación completada para CSV ID: {csv_id}")
        
        return df_numerico.to_json(orient='split')

    except Exception as e:
        logger.error(f"Error en transformación para CSV ID {csv_id}: {str(e)}")
        raise Exception(f"Error en transformación para CSV ID {csv_id}")