from celery import shared_task
from .base_imports import *
from io import StringIO
import numpy as np

def detectar_columnas_categoricas(df, target_column=None, umbral_categorico=0.05):
    """Detecta columnas categóricas automáticamente"""
    categoricas = []
    
    for col in df.columns:
        if df[col].isnull().all():
            continue
            
        # El target categórico no se normaliza
        if col == target_column:
            valores_unicos = df[col].nunique()
            if valores_unicos <= 50:  # Target de clasificación
                categoricas.append(col)
                continue
        
        # Tipo object
        if df[col].dtype == 'object':
            categoricas.append(col)
            continue
        
        # Pocos valores únicos
        valores_unicos = df[col].nunique()
        total_filas = len(df)
        ratio_unicidad = valores_unicos / total_filas
        
        if ratio_unicidad < umbral_categorico:
            categoricas.append(col)
            continue
            
        # Enteros pequeños (categóricas codificadas)
        if df[col].dtype in ['int64', 'int32']:
            if valores_unicos <= 20 and df[col].min() >= 0 and df[col].max() <= 100:
                categoricas.append(col)
    
    return categoricas

def detectar_columnas_binarias(df, target_column=None):
    """Detecta columnas binarias"""
    binarias = []
    
    for col in df.columns:
        valores_unicos = set(df[col].dropna())
        
        # Binarias numéricas (0/1, 0.0/1.0)
        if valores_unicos.issubset({0, 1, 0.0, 1.0}):
            binarias.append(col)
            continue
            
        # Si es target y tiene exactamente 2 valores, es binario
        if col == target_column and len(valores_unicos) == 2:
            binarias.append(col)
    
    return binarias

@shared_task
def preprocesar_normalizacion(df_serialized, target_column=None):
    try:
        logger.info("Iniciando normalización inteligente")
        logger.info(f"Target column: {target_column}")
        
        df = pd.read_json(StringIO(df_serialized), orient='split')
        logger.info(f"DataFrame shape: {df.shape}")
        logger.info(f"Columnas: {df.columns.tolist()}")
        
        # Detectar tipos de columnas
        categoricas = detectar_columnas_categoricas(df, target_column)
        binarias = detectar_columnas_binarias(df, target_column)
        
        # Combinar columnas que NO se deben normalizar
        no_normalizar = set(categoricas + binarias)
        
        # Obtener columnas numéricas continuas para normalizar
        columnas_numericas = df.select_dtypes(include=[np.number]).columns
        columnas_a_normalizar = [col for col in columnas_numericas if col not in no_normalizar]
        
        logger.info(f"Columnas categóricas detectadas: {categoricas}")
        logger.info(f"Columnas binarias detectadas: {binarias}")
        logger.info(f"Columnas a normalizar: {columnas_a_normalizar}")
        logger.info(f"Columnas NO normalizadas: {list(no_normalizar)}")
        
        # Normalizar solo las columnas apropiadas
        if columnas_a_normalizar:
            df_normalized = df.copy()
            scaler = StandardScaler()
            df_normalized[columnas_a_normalizar] = scaler.fit_transform(df[columnas_a_normalizar])
            logger.info(f"Normalizadas {len(columnas_a_normalizar)} columnas")
            return df_normalized.to_json(orient='split')
        else:
            logger.info("No hay columnas para normalizar")
            return df.to_json(orient='split')
        
    except Exception as e:
        logger.error(f"Error en normalización: {str(e)}")
        raise Exception("Error en normalización inteligente")