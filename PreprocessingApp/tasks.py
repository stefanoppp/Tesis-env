import os
import pandas as pd
from celery import shared_task
from django.conf import settings

from .models import CSVModel
from .preprocessing_utils import PreProcessor

@shared_task
def procesar_csv(csv_id):
    try:
        obj = CSVModel.objects.get(id=csv_id)
        file_path = obj.file.path
        df = pd.read_csv(file_path)

        processor = PreProcessor(df)
        df_processed = processor.preprocess_data()

        # Graficar
        col = obj.target_column
        outliers_img = processor.plot_comparative(df, df_processed, col, 'outliers')
        dist_img = processor.plot_comparative(df, df_processed, col, 'distributions')
        missing_img = processor.plot_missing_values(df, df_processed)

        # Guardar CSV procesado
        processed_path = file_path.replace("csv_uploads", "csv_processed")
        df_processed.to_csv(processed_path, index=False)

        obj.processed_file.name = processed_path.replace(settings.MEDIA_ROOT + os.sep, '')
        obj.report_image_outliers = outliers_img
        obj.report_image_distribution = dist_img
        obj.report_image_missing = missing_img
        obj.is_ready = True
        obj.save()

    except Exception as e:
        obj.is_ready = True
        obj.error_message = str(e)
        obj.save()
