from django.test import TestCase
from django.contrib.auth.models import User
from PreprocessingApp.models import CSVModel
from PreprocessingApp.tasks.transformacion import preprocesar_transformacion
from PreprocessingApp.tasks.imputacion import preprocesar_imputacion
from PreprocessingApp.tasks.outliers import preprocesar_outliers
from PreprocessingApp.tasks.normalizacion import preprocesar_normalizacion
from celery.result import AsyncResult
from PreprocessingApp.tasks.main import procesar_csv
from io import StringIO
import pandas as pd
import os
from django.core.files.uploadedfile import SimpleUploadedFile
class PreprocessingTasksTestCase(TestCase):

    def setUp(self):
        """Configuración inicial para las pruebas de preprocesamiento."""
        self.username = 'testuser'
        self.password = 'testpassword'
        self.user = User.objects.create_user(username=self.username, password=self.password)

        # Crear el archivo CSV de prueba usando SimpleUploadedFile
        self.csv_file = SimpleUploadedFile(
            "test.csv",
            b"column1,column2\n1,2\n3,4\n",
            content_type="text/csv"
        )

        self.csv_instance = CSVModel.objects.create(user=self.user, file=self.csv_file)
    def test_preprocesar_transformacion(self):
        """Verificar que la tarea de transformación de datos se ejecute correctamente."""
        csv_id = self.csv_instance.id
        df = pd.read_csv(self.csv_instance.file.path)
        df_serialized = df.to_json(orient='split')
        result = preprocesar_transformacion.apply(args=[df_serialized, csv_id])

        # Verificar que la tarea se completó sin errores
        self.assertEqual(result.status, "SUCCESS")

    def test_preprocesar_imputacion(self):
        """Verificar que la tarea de imputación de datos se ejecute correctamente."""
        # Serializar el DataFrame que se va a usar en la tarea de imputación
        csv_id = self.csv_instance.id
        df = pd.read_csv(self.csv_instance.file.path)
        df_serialized = df.to_json(orient='split')

        # Ejecutar la tarea de imputación
        result = preprocesar_imputacion.apply(args=[df_serialized])

        # Verificar que la tarea de imputación se completó sin errores
        self.assertEqual(result.status, "SUCCESS")

        # Puedes verificar si los valores faltantes fueron imputados correctamente
        # Esto depende de tu implementación en la tarea de imputación

    def test_preprocesar_outliers(self):
        """Verificar que la tarea de eliminación de outliers se ejecute correctamente."""
        # Crear un DataFrame de prueba
        csv_id = self.csv_instance.id
        df = pd.read_csv(self.csv_instance.file.path)
        df_serialized = df.to_json(orient='split')

        # Ejecutar la tarea de eliminación de outliers
        result = preprocesar_outliers.apply(args=[df_serialized])

        # Verificar que la tarea de outliers se completó sin errores
        self.assertEqual(result.status, "SUCCESS")

        # Comprobar si se han eliminado los outliers (esto depende de cómo implementes la lógica)
        # Para hacer esto, puedes verificar los cambios en los datos serializados

    def test_preprocesar_normalizacion(self):
        """Verificar que la tarea de normalización se ejecute correctamente."""
        # Crear un DataFrame de prueba
        csv_id = self.csv_instance.id
        df = pd.read_csv(self.csv_instance.file.path)
        df_serialized = df.to_json(orient='split')

        # Ejecutar la tarea de normalización
        result = preprocesar_normalizacion.apply(args=[df_serialized])

        # Verificar que la tarea de normalización se completó sin errores
        self.assertEqual(result.status, "SUCCESS")

        # Comprobar si la normalización se ha aplicado (esto depende de la lógica de normalización)
        # Puedes verificar el rango de los valores para asegurarte que los datos han sido normalizados
    def test_entire_preprocessing_flow(self):
        """Verificar que todo el flujo de preprocesamiento se ejecute correctamente."""
        csv_id = self.csv_instance.id

        # Ejecutar todas las tareas encadenadas de forma síncrona
        procesar_csv.apply(args=[csv_id])

        # Verificar que todo el flujo de preprocesamiento se haya completado sin errores
        csv_instance = CSVModel.objects.get(id=csv_id)
        self.assertTrue(csv_instance.is_ready)
        processed_name = os.path.basename(csv_instance.processed_file.name)
        self.assertEqual(processed_name, 'csv_procesado.csv')
        self.assertTrue(processed_name.endswith('.csv'))

    def test_preprocesamiento_no_error(self):
        """Verificar que no haya errores en el flujo de preprocesamiento."""
        csv_id = self.csv_instance.id

        # Ejecutar las tareas con un CSV válido de forma síncrona
        procesar_csv.apply(args=[csv_id])

        # Verificar que el CSV ha sido procesado correctamente sin errores
        csv_instance = CSVModel.objects.get(id=csv_id)
        self.assertEqual(csv_instance.is_ready, True)
        self.assertIsNone(csv_instance.error_message)

    def test_preprocesamiento_with_error(self):
        """Verificar que se manejen correctamente los errores en el flujo de preprocesamiento."""
        bad_csv = SimpleUploadedFile("bad_test.csv", b"", content_type="text/csv")
        bad_csv_instance = CSVModel.objects.create(user=self.user, file=bad_csv)

        csv_id = bad_csv_instance.id

        # Ejecutar las tareas con el CSV erróneo
        procesar_csv.apply(args=[csv_id])

        # Verificar que el CSV no se ha procesado correctamente
        bad_csv_instance.refresh_from_db()
        print("Mensaje de error:", bad_csv_instance.error_message)  # Opcional para depuración
        self.assertEqual(bad_csv_instance.is_ready, False)
        self.assertIsNotNone(bad_csv_instance.error_message)
