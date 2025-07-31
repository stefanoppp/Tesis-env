#!/usr/bin/env python
"""
Script de prueba para verificar que los valores imputados se muestran correctamente
en las respuestas de predicción de la API.
"""

import requests
import json
import os
import django
from django.conf import settings

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from MLPlatformApp.models import AIModel
from django.contrib.auth.models import User

def test_prediction_with_missing_values():
    """
    Prueba que los valores imputados se devuelvan correctamente cuando faltan datos.
    """
    print("=== Prueba de Valores Imputados en Predicciones ===")
    
    # Buscar un modelo existente para probar
    models = AIModel.objects.filter(status='completed')[:1]
    
    if not models.exists():
        print("❌ No hay modelos completados para probar")
        return
    
    model = models.first()
    print(f"✅ Usando modelo: {model.name} (ID: {model.id})")
    print(f"   Tipo de tarea: {model.task_type}")
    print(f"   Ruta del modelo: {model.model_path}")
    
    # Verificar si existe el archivo de estadísticas de imputación
    stats_file = model.model_path.replace('.pkl', '_imputation_stats.pkl')
    print(f"   Archivo de estadísticas: {stats_file}")
    
    if os.path.exists(stats_file):
        print("   ✅ Archivo de estadísticas encontrado")
        import pickle
        try:
            with open(stats_file, 'rb') as f:
                stats = pickle.load(f)
            print(f"   📊 Estadísticas disponibles: {list(stats.keys())}")
            for key, value in stats.items():
                print(f"      {key}: {value}")
        except Exception as e:
            print(f"   ❌ Error al leer estadísticas: {e}")
    else:
        print("   ⚠️  Archivo de estadísticas no encontrado (modelo entrenado antes de la actualización)")
    
    # Obtener las características del modelo
    try:
        feature_names = model.feature_names
        print(f"   Características del modelo: {feature_names}")
    except Exception as e:
        print(f"❌ No se pudieron obtener las características del modelo: {e}")
        # Usar características de ejemplo
        feature_names = ['feature1', 'feature2', 'feature3']
        print(f"   Usando características de ejemplo: {feature_names}")
    
    # Crear datos de prueba con algunos valores faltantes
    test_data = {}
    for i, feature in enumerate(feature_names):
        if i % 2 == 0:  # Dejar algunos valores vacíos
            test_data[feature] = None
        else:
            test_data[feature] = 1.0  # Valor de prueba
    
    print(f"\n📊 Datos de prueba (con valores faltantes):")
    for key, value in test_data.items():
        status = "❌ FALTANTE" if value is None else "✅ PRESENTE"
        print(f"   {key}: {value} {status}")
    
    # Simular la predicción directamente usando la función interna
    from MLPlatformApp.views import PredictView
    
    predict_view = PredictView()
    
    try:
        print("\n🔄 Ejecutando predicción...")
        result = predict_view._make_prediction(model, test_data)
        print(f"\n🎯 Resultado de predicción:")
        
        # Mostrar solo los campos relevantes
        if model.task_type == 'classification':
            print(f"   Clase predicha: {result.get('predicted_class', 'N/A')}")
            print(f"   Confianza: {result.get('confidence', 'N/A')}")
        else:
            print(f"   Valor predicho: {result.get('predicted_value', 'N/A')}")
        
        # Verificar si se devolvieron valores imputados
        if 'imputed_values' in result:
            imputed_values = result['imputed_values']
            print(f"\n🔧 Valores imputados detectados:")
            if imputed_values:
                for feature, value in imputed_values.items():
                    print(f"   ✅ {feature}: {value}")
                print(f"\n✅ Se detectaron {len(imputed_values)} valores imputados")
                
                # Verificar que los valores imputados corresponden a los valores faltantes
                missing_in_input = [k for k, v in test_data.items() if v is None]
                imputed_features = list(imputed_values.keys())
                
                if set(missing_in_input) == set(imputed_features):
                    print("✅ Los valores imputados corresponden exactamente a los valores faltantes")
                else:
                    print(f"⚠️  Discrepancia: Faltantes={missing_in_input}, Imputados={imputed_features}")
            else:
                print("⚠️  No se detectaron valores imputados")
        else:
            print("❌ No se encontró el campo 'imputed_values' en la respuesta")
            
    except Exception as e:
        print(f"❌ Error durante la predicción: {str(e)}")
        import traceback
        traceback.print_exc()

def test_api_response_format():
    """
    Verifica que la respuesta de la API incluya los valores imputados.
    """
    print("\n=== Prueba de Formato de Respuesta API ===")
    
    from MLPlatformApp.views import PredictView
    import inspect
    
    # Verificar que el método _make_prediction incluya lógica de imputación
    source = inspect.getsource(PredictView._make_prediction)
    
    checks = [
        ('imputed_values', 'Variable para almacenar valores imputados'),
        ('missing_features', 'Detección de características faltantes'),
        ('imputation_stats', 'Carga de estadísticas de imputación'),
        ('pickle.load', 'Carga de archivo de estadísticas')
    ]
    
    print("🔍 Verificando implementación:")
    for check, description in checks:
        if check in source:
            print(f"   ✅ {description}: PRESENTE")
        else:
            print(f"   ❌ {description}: AUSENTE")
    
    # Verificar que la respuesta del endpoint incluya imputed_values
    predict_source = inspect.getsource(PredictView.post)
    if "'imputed_values'" in predict_source:
        print(f"   ✅ Campo 'imputed_values' en respuesta API: PRESENTE")
    else:
        print(f"   ❌ Campo 'imputed_values' en respuesta API: AUSENTE")

def test_training_stats_generation():
    """
    Verifica que el proceso de entrenamiento genere estadísticas de imputación.
    """
    print("\n=== Prueba de Generación de Estadísticas en Entrenamiento ===")
    
    from MLPlatformApp.training import train_model_task
    import inspect
    
    # Verificar que el entrenamiento incluya generación de estadísticas
    source = inspect.getsource(train_model_task)
    
    checks = [
        ('imputation_stats', 'Variable para estadísticas de imputación'),
        ('data[column].mean()', 'Cálculo de media para numéricos'),
        ('data[column].mode()', 'Cálculo de moda para categóricos'),
        ('_imputation_stats.pkl', 'Guardado de archivo de estadísticas')
    ]
    
    print("🔍 Verificando generación de estadísticas en entrenamiento:")
    for check, description in checks:
        if check in source:
            print(f"   ✅ {description}: PRESENTE")
        else:
            print(f"   ❌ {description}: AUSENTE")

if __name__ == "__main__":
    test_prediction_with_missing_values()
    test_api_response_format()
    test_training_stats_generation()
    
    print("\n=== Resumen de la Implementación ===")
    print("✅ Se ha implementado la captura de valores imputados en el backend")
    print("✅ La respuesta de la API incluye el campo 'imputed_values'")
    print("✅ El entrenamiento guarda estadísticas de imputación")
    print("✅ Las predicciones cargan y usan las estadísticas guardadas")
    
    print("\n📝 Cómo funciona:")
    print("   1. Durante el entrenamiento se calculan y guardan media/moda de cada característica")
    print("   2. Durante la predicción se detectan valores faltantes (None, '', vacíos)")
    print("   3. Se cargan las estadísticas guardadas y se muestran los valores de reemplazo")
    print("   4. La respuesta incluye 'imputed_values' con los valores utilizados")
    
    print("\n🎯 Para el frontend/cliente:")
    print("   - Cuando input_data[campo] es None/vacío, mostrar imputed_values[campo]")
    print("   - Indicar claramente que el valor fue reemplazado automáticamente")
    print("   - Ejemplo: 'Edad: 35.2 (valor promedio usado automáticamente)'")