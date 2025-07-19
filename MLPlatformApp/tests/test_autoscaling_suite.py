#!/usr/bin/env python
"""
Suite de pruebas completa para el sistema de autoescalado dinámico.

Este archivo organiza y ejecuta todas las pruebas relacionadas con:
- Política de escalado dinámico
- Monitoreo de escalado
- Integración con Celery
- Escenarios de estrés
- Prevención de saturación

Uso:
    python manage.py test MLPlatformApp.tests.test_autoscaling_suite
    
O para ejecutar pruebas específicas:
    python manage.py test MLPlatformApp.tests.test_autoscaling_suite.AutoscalingTestSuite.test_basic_functionality
"""

import unittest
import sys
import os
from django.test import TestCase

# Importar todos los módulos de pruebas
from .test_autoscaling import (
    TestDynamicScalingPolicy,
    TestAutoScalingTriggers,
    TestSystemSaturationPrevention,
    TestIntegrationScaling
)
from .test_scaling_monitor import (
    TestScalingMonitorCommand,
    TestScalingMonitorIntegration,
    TestScalingPerformance
)
from .test_celery_integration import (
    TestCeleryIntegration,
    TestWorkerScalingBehavior,
    TestCeleryAutoscaleIntegration,
    TestCeleryTaskExecution,
    TestScalingMetrics
)
from .test_stress_scenarios import (
    TestStressScenarios,
    TestSystemSaturationPrevention as TestStressSaturation,
    TestEdgeCases,
    TestPerformanceUnderLoad
)


class AutoscalingTestSuite(TestCase):
    """Suite principal de pruebas de autoescalado"""
    
    @classmethod
    def setUpClass(cls):
        """Configuración inicial de la suite"""
        super().setUpClass()
        print("\n" + "="*80)
        print("INICIANDO SUITE DE PRUEBAS DE AUTOESCALADO DINÁMICO")
        print("="*80)
    
    @classmethod
    def tearDownClass(cls):
        """Limpieza final de la suite"""
        super().tearDownClass()
        print("\n" + "="*80)
        print("SUITE DE PRUEBAS DE AUTOESCALADO COMPLETADA")
        print("="*80)
    
    def test_basic_functionality(self):
        """Test básico para verificar que la suite funciona"""
        self.assertTrue(True, "Suite de autoescalado inicializada correctamente")
    
    def test_imports_successful(self):
        """Verificar que todos los módulos se importan correctamente"""
        # Verificar que las clases de prueba están disponibles
        test_classes = [
            TestDynamicScalingPolicy,
            TestAutoScalingTriggers,
            TestSystemSaturationPrevention,
            TestIntegrationScaling,
            TestScalingMonitorCommand,
            TestCeleryIntegration,
            TestStressScenarios
        ]
        
        for test_class in test_classes:
            self.assertTrue(
                issubclass(test_class, TestCase),
                f"{test_class.__name__} debería ser una subclase de TestCase"
            )


def create_test_suite():
    """Crear suite de pruebas personalizada"""
    suite = unittest.TestSuite()
    
    # Pruebas básicas de política de escalado
    suite.addTest(unittest.makeSuite(TestDynamicScalingPolicy))
    
    # Pruebas de triggers y monitoreo
    suite.addTest(unittest.makeSuite(TestAutoScalingTriggers))
    suite.addTest(unittest.makeSuite(TestScalingMonitorCommand))
    suite.addTest(unittest.makeSuite(TestScalingMonitorIntegration))
    
    # Pruebas de integración con Celery
    suite.addTest(unittest.makeSuite(TestCeleryIntegration))
    suite.addTest(unittest.makeSuite(TestWorkerScalingBehavior))
    suite.addTest(unittest.makeSuite(TestCeleryAutoscaleIntegration))
    
    # Pruebas de prevención de saturación
    suite.addTest(unittest.makeSuite(TestSystemSaturationPrevention))
    suite.addTest(unittest.makeSuite(TestStressSaturation))
    
    # Pruebas de estrés y casos extremos
    suite.addTest(unittest.makeSuite(TestStressScenarios))
    suite.addTest(unittest.makeSuite(TestEdgeCases))
    
    # Pruebas de rendimiento
    suite.addTest(unittest.makeSuite(TestPerformanceUnderLoad))
    suite.addTest(unittest.makeSuite(TestScalingPerformance))
    
    # Pruebas de integración completa
    suite.addTest(unittest.makeSuite(TestIntegrationScaling))
    
    return suite


def run_quick_tests():
    """Ejecutar solo las pruebas más importantes y rápidas"""
    suite = unittest.TestSuite()
    
    # Pruebas críticas básicas
    suite.addTest(TestDynamicScalingPolicy('test_scale_up_with_long_queue'))
    suite.addTest(TestDynamicScalingPolicy('test_scale_down_with_high_cpu'))
    suite.addTest(TestDynamicScalingPolicy('test_safety_limits_prevent_overload'))
    
    # Pruebas de triggers
    suite.addTest(TestAutoScalingTriggers('test_immediate_trigger_on_critical_cpu'))
    suite.addTest(TestAutoScalingTriggers('test_no_trigger_on_normal_conditions'))
    
    # Pruebas de integración básica
    suite.addTest(TestCeleryIntegration('test_get_dynamic_celery_config'))
    suite.addTest(TestWorkerScalingBehavior('test_worker_scaling_consistency'))
    
    # Pruebas de saturación críticas
    suite.addTest(TestSystemSaturationPrevention('test_prevents_system_overload'))
    
    return suite


def run_stress_tests():
    """Ejecutar solo las pruebas de estrés"""
    suite = unittest.TestSuite()
    
    # Todas las pruebas de estrés
    suite.addTest(unittest.makeSuite(TestStressScenarios))
    suite.addTest(unittest.makeSuite(TestEdgeCases))
    suite.addTest(unittest.makeSuite(TestPerformanceUnderLoad))
    
    return suite


def run_integration_tests():
    """Ejecutar solo las pruebas de integración"""
    suite = unittest.TestSuite()
    
    # Pruebas de integración
    suite.addTest(unittest.makeSuite(TestCeleryIntegration))
    suite.addTest(unittest.makeSuite(TestCeleryAutoscaleIntegration))
    suite.addTest(unittest.makeSuite(TestCeleryTaskExecution))
    suite.addTest(unittest.makeSuite(TestIntegrationScaling))
    
    return suite


class TestSuiteRunner:
    """Runner personalizado para las pruebas de autoescalado"""
    
    def __init__(self, verbosity=2):
        self.verbosity = verbosity
    
    def run_all_tests(self):
        """Ejecutar todas las pruebas"""
        print("\n🚀 Ejecutando TODAS las pruebas de autoescalado...")
        suite = create_test_suite()
        runner = unittest.TextTestRunner(verbosity=self.verbosity)
        result = runner.run(suite)
        return result
    
    def run_quick_tests(self):
        """Ejecutar pruebas rápidas"""
        print("\n⚡ Ejecutando pruebas RÁPIDAS de autoescalado...")
        suite = run_quick_tests()
        runner = unittest.TextTestRunner(verbosity=self.verbosity)
        result = runner.run(suite)
        return result
    
    def run_stress_tests(self):
        """Ejecutar pruebas de estrés"""
        print("\n💪 Ejecutando pruebas de ESTRÉS de autoescalado...")
        suite = run_stress_tests()
        runner = unittest.TextTestRunner(verbosity=self.verbosity)
        result = runner.run(suite)
        return result
    
    def run_integration_tests(self):
        """Ejecutar pruebas de integración"""
        print("\n🔗 Ejecutando pruebas de INTEGRACIÓN de autoescalado...")
        suite = run_integration_tests()
        runner = unittest.TextTestRunner(verbosity=self.verbosity)
        result = runner.run(suite)
        return result
    
    def print_test_summary(self, result):
        """Imprimir resumen de las pruebas"""
        print("\n" + "="*60)
        print("RESUMEN DE PRUEBAS DE AUTOESCALADO")
        print("="*60)
        print(f"Pruebas ejecutadas: {result.testsRun}")
        print(f"Errores: {len(result.errors)}")
        print(f"Fallos: {len(result.failures)}")
        print(f"Omitidas: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
        
        if result.errors:
            print("\n❌ ERRORES:")
            for test, error in result.errors:
                error_first_line = error.split('\n')[0]
                print(f"  - {test}: {error_first_line}")
        
        if result.failures:
            print("\n❌ FALLOS:")
            for test, failure in result.failures:
                failure_first_line = failure.split('\n')[0]
                print(f"  - {test}: {failure_first_line}")
        
        if result.wasSuccessful():
            print("\n✅ ¡TODAS LAS PRUEBAS PASARON!")
        else:
            print("\n❌ Algunas pruebas fallaron.")
        
        print("="*60)


def main():
    """Función principal para ejecutar desde línea de comandos"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Suite de pruebas de autoescalado')
    parser.add_argument('--quick', action='store_true', 
                       help='Ejecutar solo pruebas rápidas')
    parser.add_argument('--stress', action='store_true', 
                       help='Ejecutar solo pruebas de estrés')
    parser.add_argument('--integration', action='store_true', 
                       help='Ejecutar solo pruebas de integración')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Salida verbosa')
    
    args = parser.parse_args()
    
    verbosity = 2 if args.verbose else 1
    runner = TestSuiteRunner(verbosity=verbosity)
    
    if args.quick:
        result = runner.run_quick_tests()
    elif args.stress:
        result = runner.run_stress_tests()
    elif args.integration:
        result = runner.run_integration_tests()
    else:
        result = runner.run_all_tests()
    
    runner.print_test_summary(result)
    
    # Salir con código de error si hay fallos
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()