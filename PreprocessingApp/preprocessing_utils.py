import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from scipy import stats
import seaborn as sns
import matplotlib.pyplot as plt
import base64
import io
import os
from django.conf import settings 
class PreProcessor:
    def __init__(self, data: pd.DataFrame):
        self.data = data

    def preprocess_data(self) -> pd.DataFrame:
        """Realiza el preprocesamiento de datos: imputación, eliminación de outliers y normalización"""
        df = self.data.copy()

        # Imputación: reemplazo de valores nulos con la media de la columna
        df = self.impute_data(df)
        
        # Eliminar outliers
        df = self.remove_outliers(df)

        # Normalización: escalar los datos
        df = self.normalize_data(df)

        return df

    def impute_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Imputa los valores nulos con la media de la columna"""
        imputer = SimpleImputer(strategy='mean')
        df[df.select_dtypes(include=['float64', 'int64']).columns] = imputer.fit_transform(df.select_dtypes(include=['float64', 'int64']))
        return df
    
    def remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Elimina los outliers usando z-score"""
        z_scores = stats.zscore(df.select_dtypes(include=['float64', 'int64']))
        return df[(abs(z_scores) < 3).all(axis=1)]
    
    def normalize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza el DataFrame recibido, escalando las características"""
        df[df.select_dtypes(include=['float64', 'int64']).columns] = StandardScaler().fit_transform(df[df.select_dtypes(include=['float64', 'int64']).columns])
        return df
    
    def plot_comparative(self, df_original: pd.DataFrame, df_processed: pd.DataFrame, column: str, plot_type: str) -> str:
        """Genera gráficos comparativos entre datos originales y procesados en base64 (outliers o distribuciones)"""
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Gráficos de outliers
        if plot_type == 'outliers':
            sns.boxplot(x=df_original[column], ax=axes[0])
            sns.boxplot(x=df_processed[column], ax=axes[1])

        # Gráficos de distribuciones
        elif plot_type == 'distributions':
            sns.histplot(df_original[column], kde=True, ax=axes[0])
            sns.histplot(df_processed[column], kde=True, ax=axes[1])

        plt.tight_layout()
        return self.fig_to_base64(fig)

    def plot_missing_values(self, df_original: pd.DataFrame, df_processed: pd.DataFrame) -> str:
        """Genera un gráfico de heatmap comparativo entre valores nulos en base64"""
        fig, axes = plt.subplots(1, 2, figsize=(12, 6))
        sns.heatmap(df_original.isnull(), cbar=False, cmap='viridis', ax=axes[0])
        sns.heatmap(df_processed.isnull(), cbar=False, cmap='viridis', ax=axes[1])
        plt.tight_layout()
        return self.fig_to_base64(fig)

    def fig_to_base64(self, figure) -> str:
        """Convierte una figura de matplotlib a base64"""
        buf = io.BytesIO()
        figure.savefig(buf, format='png', bbox_inches='tight')
        plt.close(figure)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    