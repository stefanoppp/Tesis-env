#!/usr/bin/env python
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    # Configurar Django settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    
    # Agregar el directorio actual al path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Configurar Django
    django.setup()
    
    # Importar y ejecutar los tests
    import unittest
    
    # Importar los módulos de test
    try:
        from MLPlatformApp.tests.test_gpu_detection import *
        from MLPlatformApp.tests.test_flower_gpu_exclusion import *
        
        # Ejecutar los tests
        if __name__ == '__main__':
            unittest.main(verbosity=2)
    except ImportError as e:
        print(f"Error importing test modules: {e}")
        
        # Ejecutar tests de forma alternativa
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # Cargar tests desde archivos
        test_dir = 'MLPlatformApp/tests'
        tests = loader.discover(test_dir, pattern='test_*.py')
        suite.addTests(tests)
        
        # Ejecutar tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Salir con código de error si hay fallos
        sys.exit(not result.wasSuccessful())