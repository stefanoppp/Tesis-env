from celery import shared_task
import pandas as pd
from .base_imports import *
from io import StringIO

@shared_task
def preprocesar_duplicados(df_serialized):
    try:
        logger.info(f"Iniciando eliminación de duplicados")

        # Convertir el string JSON en DataFrame
        df = pd.read_json(StringIO(df_serialized), orient='split')
        
        filas_originales = len(df)
        columnas_originales = len(df.columns)
        
        logger.info(f"DataFrame inicial: {filas_originales} filas, {columnas_originales} columnas")

        # 1. Eliminar columnas completamente duplicadas
        df_sin_cols_dup = df.loc[:, ~df.T.duplicated()]
        columnas_eliminadas = columnas_originales - len(df_sin_cols_dup.columns)
        
        if columnas_eliminadas > 0:
            logger.info(f"Columnas duplicadas eliminadas: {columnas_eliminadas}")
        
        # 2. Eliminar filas duplicadas
        # Primero identificar duplicados para logging
        filas_duplicadas = df_sin_cols_dup.duplicated().sum()
        
        # Eliminar filas duplicadas manteniendo la primera ocurrencia
        df_final = df_sin_cols_dup.drop_duplicates(keep='first')
        
        filas_finales = len(df_final)
        filas_eliminadas = filas_originales - filas_finales
        
        logger.info(f"Filas duplicadas identificadas: {filas_duplicadas}")
        logger.info(f"Filas eliminadas: {filas_eliminadas}")
        logger.info(f"DataFrame final: {filas_finales} filas, {len(df_final.columns)} columnas")
        
        # Verificar que el DataFrame no esté vacío
        if df_final.empty:
            logger.warning("El DataFrame quedó vacío después de eliminar duplicados")
            # Devolver el DataFrame original si el resultado está vacío
            logger.info("Devolviendo DataFrame original para evitar pérdida total de datos")
            return df.to_json(orient='split')
        
        # Verificar que tengamos al menos algunas filas
        if len(df_final) < 2:
            logger.warning(f"Solo quedan {len(df_final)} filas después de eliminar duplicados")
        
        logger.info(f"Eliminación de duplicados completada para CSV")
        logger.info(f"Columnas resultantes después de eliminar duplicados: {df_final.columns.tolist()}")
        
        return df_final.to_json(orient='split')
        
    except Exception as e:
        logger.error(f"Error en eliminación de duplicados: {str(e)}")
        raise Exception("Error en eliminación de duplicados")


@shared_task
def preprocesar_duplicados_avanzado(df_serialized, eliminar_filas=True, eliminar_columnas=True, 
                                   subset_columns=None, keep_strategy='first'):
    """
    Versión avanzada de eliminación de duplicados con más opciones de configuración
    
    Args:
        df_serialized: DataFrame serializado en JSON
        eliminar_filas: Bool, si eliminar filas duplicadas
        eliminar_columnas: Bool, si eliminar columnas duplicadas
        subset_columns: Lista de columnas a considerar para duplicados de filas (None = todas)
        keep_strategy: 'first', 'last' o False (eliminar todas las duplicadas)
    """
    try:
        logger.info(f"Iniciando eliminación avanzada de duplicados")
        logger.info(f"Parámetros: filas={eliminar_filas}, columnas={eliminar_columnas}, "
                   f"subset={subset_columns}, keep={keep_strategy}")

        # Convertir el string JSON en DataFrame
        df = pd.read_json(StringIO(df_serialized), orient='split')
        
        filas_originales = len(df)
        columnas_originales = len(df.columns)
        
        logger.info(f"DataFrame inicial: {filas_originales} filas, {columnas_originales} columnas")

        df_resultado = df.copy()

        # 1. Eliminar columnas duplicadas si está habilitado
        if eliminar_columnas:
            df_resultado = df_resultado.loc[:, ~df_resultado.T.duplicated()]
            columnas_eliminadas = columnas_originales - len(df_resultado.columns)
            
            if columnas_eliminadas > 0:
                logger.info(f"Columnas duplicadas eliminadas: {columnas_eliminadas}")
                cols_restantes = df_resultado.columns.tolist()
                logger.info(f"Columnas restantes: {cols_restantes}")

        # 2. Eliminar filas duplicadas si está habilitado
        if eliminar_filas:
            # Determinar columnas a considerar para duplicados
            columns_to_check = subset_columns if subset_columns else None
            
            if columns_to_check:
                # Verificar que las columnas existan en el DataFrame
                columns_to_check = [col for col in columns_to_check if col in df_resultado.columns]
                if not columns_to_check:
                    logger.warning("Ninguna de las columnas especificadas existe en el DataFrame")
                    columns_to_check = None
            
            # Contar duplicados antes de eliminar
            if columns_to_check:
                filas_duplicadas = df_resultado.duplicated(subset=columns_to_check, keep=False).sum()
                df_resultado = df_resultado.drop_duplicates(subset=columns_to_check, keep=keep_strategy)
            else:
                filas_duplicadas = df_resultado.duplicated(keep=False).sum()
                df_resultado = df_resultado.drop_duplicates(keep=keep_strategy)
            
            filas_finales = len(df_resultado)
            filas_eliminadas = filas_originales - filas_finales
            
            logger.info(f"Filas duplicadas identificadas: {filas_duplicadas}")
            logger.info(f"Filas eliminadas: {filas_eliminadas}")

        logger.info(f"DataFrame final: {len(df_resultado)} filas, {len(df_resultado.columns)} columnas")
        
        # Verificaciones de seguridad
        if df_resultado.empty:
            logger.warning("El DataFrame quedó vacío después de eliminar duplicados")
            logger.info("Devolviendo DataFrame original para evitar pérdida total de datos")
            return df.to_json(orient='split')
        
        if len(df_resultado) < 2:
            logger.warning(f"Solo quedan {len(df_resultado)} filas después de eliminar duplicados")
        
        logger.info(f"Eliminación avanzada de duplicados completada")
        
        return df_resultado.to_json(orient='split')
        
    except Exception as e:
        logger.error(f"Error en eliminación avanzada de duplicados: {str(e)}")
        raise Exception("Error en eliminación avanzada de duplicados")