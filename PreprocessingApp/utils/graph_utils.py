import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from scipy import stats
import os

def generar_graficos_calidad_comparativo(df_orig, df_proc, output_dir):
    img_dir = os.path.join(output_dir, 'imgs', 'calidad')
    os.makedirs(img_dir, exist_ok=True)

    # Porcentaje de valores faltantes
    perc_missing_orig = (df_orig.isnull().sum().sum() / df_orig.size) * 100 if df_orig.size > 0 else 0
    perc_missing_proc = (df_proc.isnull().sum().sum() / df_proc.size) * 100 if df_proc.size > 0 else 0
    plt.figure(figsize=(6, 4))
    plt.bar(['Original', 'Procesado'], [perc_missing_orig, perc_missing_proc], color=['blue', 'green'])
    plt.title('Porcentaje de valores faltantes')
    plt.ylabel('Porcentaje (%)')
    plt.savefig(os.path.join(img_dir, 'valores_faltantes_comparativo.png'), bbox_inches='tight', dpi=300)
    plt.close()

    # Porcentaje de filas duplicadas
    perc_dup_orig = (df_orig.duplicated().sum() / len(df_orig)) * 100 if len(df_orig) > 0 else 0
    perc_dup_proc = (df_proc.duplicated().sum() / len(df_proc)) * 100 if len(df_proc) > 0 else 0
    plt.figure(figsize=(6, 4))
    plt.bar(['Original', 'Procesado'], [perc_dup_orig, perc_dup_proc], color=['blue', 'green'])
    plt.title('Porcentaje de filas duplicadas')
    plt.ylabel('Porcentaje (%)')
    plt.savefig(os.path.join(img_dir, 'filas_duplicadas_comparativo.png'), bbox_inches='tight', dpi=300)
    plt.close()

    # Porcentaje de valores anómalos
    def calc_outliers(df):
        numeric = df.select_dtypes(include=[np.number])
        if numeric.empty:
            return 0
        Q1 = numeric.quantile(0.25)
        Q3 = numeric.quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR
        outliers = ((numeric < lower) | (numeric > upper)).sum().sum()
        total_values = numeric.size - numeric.isnull().sum().sum()
        return (outliers / total_values) * 100 if total_values > 0 else 0

    perc_out_orig = calc_outliers(df_orig)
    perc_out_proc = calc_outliers(df_proc)
    plt.figure(figsize=(6, 4))
    plt.bar(['Original', 'Procesado'], [perc_out_orig, perc_out_proc], color=['blue', 'green'])
    plt.title('Porcentaje de valores anómalos')
    plt.ylabel('Porcentaje (%)')
    plt.savefig(os.path.join(img_dir, 'valores_anomalos_comparativo.png'), bbox_inches='tight', dpi=300)
    plt.close()

    # KDE z-scores
    def get_zscores(df):
        numeric = df.select_dtypes(include=[np.number])
        if numeric.empty:
            return np.array([])
        z = (numeric - numeric.mean()) / numeric.std()
        return z.values.flatten()

    z_orig = get_zscores(df_orig)
    z_proc = get_zscores(df_proc)
    z_orig = z_orig[~np.isnan(z_orig)]
    z_proc = z_proc[~np.isnan(z_proc)]

    plt.figure(figsize=(8, 5))
    if len(z_orig) > 0:
        sns.kdeplot(z_orig, label='Original')
    if len(z_proc) > 0:
        sns.kdeplot(z_proc, label='Procesado')
    x = np.linspace(-5, 5, 100)
    sns.lineplot(x=x, y=stats.norm.pdf(x, 0, 1), label='Normal (0,1)', color='red')
    plt.title('KDE de z-scores comparativo')
    plt.xlabel('z-score')
    plt.ylabel('Densidad')
    plt.legend()
    plt.savefig(os.path.join(img_dir, 'kde_zscores_comparativo.png'), bbox_inches='tight', dpi=300)
    plt.close()
