import os
import numpy as np
from sklearn.feature_selection import mutual_info_regression
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

from sklearn.feature_selection import mutual_info_regression, mutual_info_classif
from sklearn.preprocessing import LabelEncoder
def max_abs_correlation(df):
    num_df = df.select_dtypes(include=[np.number])
    if num_df.shape[1] < 2:
        return None  # No hay correlación si hay menos de 2 columnas numéricas
    corr = num_df.corr().abs()
    np.fill_diagonal(corr.values, 0)  # Ignora la diagonal
    return float(corr.max().max())

def contar_outliers(df):
    """
    Cuenta outliers usando el criterio de 1.5*IQR para todas las columnas numéricas.
    """
    count = 0
    for col in df.select_dtypes(include=[np.number]).columns:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        count += ((df[col] < lower) | (df[col] > upper)).sum()
    return int(count)
def calcular_informacion_mutua(df, target_column):
    print("Columnas del DataFrame:", list(df.columns))
    print("Target column recibido:", repr(target_column))
    columnas = [str(col).strip() for col in df.columns]
    target_column_norm = target_column.strip()
    if target_column_norm not in columnas:
        print(f"ERROR: La columna objetivo '{target_column}' no está en el DataFrame. Columnas: {columnas}")
        return {}
    real_target = df.columns[columnas.index(target_column_norm)]
    y = df[real_target]
    X = df.select_dtypes(include=[np.number]).drop(columns=[real_target], errors='ignore')
    if df.shape[0] <= 3:
        print("No se puede calcular información mutua: muy pocas filas tras el preprocesamiento.")
        return {}
    try:
        # Si el target es numérico, usa mutual_info_regression
        if pd.api.types.is_numeric_dtype(y):
            mi = mutual_info_regression(X.fillna(0), y)
        else:
            # Si es categórico, lo codifica y usa mutual_info_classif
            y_encoded = LabelEncoder().fit_transform(y.astype(str))
            mi = mutual_info_classif(X.fillna(0), y_encoded)
        return {col: float(val) for col, val in zip(X.columns, mi)}
    except Exception as e:
        print("Error en mutual_info:", e)
        return {}
def calcular_metricas_comparativas_json(path_csv_original, path_csv_preprocesado,target_column):
    df_orig = pd.read_csv(path_csv_original)
    df_proc = pd.read_csv(path_csv_preprocesado)

    def mean_absolute_deviation(df):
        num_df = df.select_dtypes(include=[np.number])
        return (num_df - num_df.mean()).abs().mean().mean()

    metricas = {
        "Valores faltantes": {
            "csv_normal": int(df_orig.isnull().sum().sum()),
            "csv_preprocesado": int(df_proc.isnull().sum().sum())
        },
        "Valores anómalos (outliers)": {
            "csv_normal": contar_outliers(df_orig),
            "csv_preprocesado": contar_outliers(df_proc)
        },
        "Mean Deviation": {
            "csv_normal": float(mean_absolute_deviation(df_orig)),
            "csv_preprocesado": float(mean_absolute_deviation(df_proc))
        },
        "Std Deviation Error": {
            "csv_normal": float(df_orig.select_dtypes(include=[np.number]).std().mean()),
            "csv_preprocesado": float(df_proc.select_dtypes(include=[np.number]).std().mean())
        },
        "Máxima correlación absoluta": {
            "csv_normal": max_abs_correlation(df_orig),
            "csv_preprocesado": max_abs_correlation(df_proc)
        },
        "Info mutua": {
            "csv_normal": calcular_informacion_mutua(df_orig, target_column),
            "csv_preprocesado": calcular_informacion_mutua(df_proc, target_column)
        }
    }
    return metricas