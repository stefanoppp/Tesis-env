import base64
import io
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from scipy import stats
import seaborn as sns

class PreProcessor:
    def __init__(self, data: pd.DataFrame):
        self.data = data

    def preprocess_data(self) -> pd.DataFrame:
        df = self.data.copy()
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns

        # Imputación de nulos
        imputer = SimpleImputer(strategy='mean')
        df[numeric_cols] = imputer.fit_transform(df[numeric_cols])

        # Eliminar outliers
        z_scores = stats.zscore(df[numeric_cols])
        df = df[(abs(z_scores) < 3).all(axis=1)]

        # Normalización
        df[numeric_cols] = StandardScaler().fit_transform(df[numeric_cols])

        return df

    def plot_comparative(self, df_original: pd.DataFrame, df_processed: pd.DataFrame, column: str, plot_type: str) -> str:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        if plot_type == 'outliers':
            sns.boxplot(x=df_original[column], ax=axes[0])
            sns.boxplot(x=df_processed[column], ax=axes[1])
            axes[0].set_title("Original")
            axes[1].set_title("Procesado")
        elif plot_type == 'distributions':
            sns.histplot(df_original[column], kde=True, ax=axes[0])
            sns.histplot(df_processed[column], kde=True, ax=axes[1])
            axes[0].set_title("Original")
            axes[1].set_title("Procesado")

        plt.tight_layout()
        return self.fig_to_base64(fig)

    def plot_missing_values(self, df_original: pd.DataFrame, df_processed: pd.DataFrame) -> str:
        fig, axes = plt.subplots(1, 2, figsize=(12, 6))
        sns.heatmap(df_original.isnull(), cbar=False, cmap='viridis', ax=axes[0])
        sns.heatmap(df_processed.isnull(), cbar=False, cmap='viridis', ax=axes[1])
        axes[0].set_title("Nulos Original")
        axes[1].set_title("Nulos Procesado")
        plt.tight_layout()
        return self.fig_to_base64(fig)

    def fig_to_base64(self, figure) -> str:
        buf = io.BytesIO()
        figure.savefig(buf, format='png', bbox_inches='tight')
        plt.close(figure)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
