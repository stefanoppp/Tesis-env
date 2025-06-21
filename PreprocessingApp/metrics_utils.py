import pandas as pd
import numpy as np

def calcular_metricas_comparativas_json(path_csv_original, path_csv_preprocesado):
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
        }
    }
    return metricas

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