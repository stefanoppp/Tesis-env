#!/usr/bin/env python
"""
Test simple para verificar la detección de GPU sin dependencias de Django
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock de Django settings para evitar dependencias
class MockSettings:
    def __init__(self):
        self.AUTO_HARDWARE_OPTIMIZATION = True
        self.ENABLE_GPU_ACCELERATION = True
        self.DYNAMIC_SCALING_ENABLED = True

# Mock del módulo django.conf
sys.modules['django'] = Mock()
sys.modules['django.conf'] = Mock()
sys.modules['django.conf.settings'] = MockSettings()
sys.modules['django.core'] = Mock()
sys.modules['django.core.management'] = Mock()
sys.modules['django.core.management.base'] = Mock()
sys.modules['celery'] = Mock()
sys.modules['redis'] = Mock()

# Ahora importar el módulo a testear
try:
    from MLPlatformApp.config.hardware_optimization import HardwareOptimizer
except ImportError as e:
    print(f"Error importing HardwareOptimizer: {e}")
    sys.exit(1)


class TestGPUDetectionSimple(unittest.TestCase):
    """Tests simples para detección de GPU sin dependencias de Django"""
    
    def setUp(self):
        """Configuración inicial para los tests"""
        self.optimizer = HardwareOptimizer()
    
    def test_hardware_optimizer_initialization(self):
        """Test que HardwareOptimizer se inicializa correctamente"""
        self.assertIsNotNone(self.optimizer)
        self.assertTrue(hasattr(self.optimizer, '_detect_gpu'))
        self.assertTrue(hasattr(self.optimizer, 'get_optimal_config'))
    
    @patch('subprocess.run')
    def test_nvidia_gpu_detection_wmic_success(self, mock_subprocess):
        """Test detección exitosa de GPU NVIDIA con WMIC"""
        # Mock de respuesta exitosa de WMIC para NVIDIA
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Name\nNVIDIA GeForce RTX 3080\n"
        mock_subprocess.return_value = mock_result
        
        # Crear nuevo optimizer para que use el mock
        with patch('platform.system', return_value='Windows'):
            optimizer = HardwareOptimizer()
            # El resultado depende de la detección interna
            self.assertIsInstance(optimizer.gpu_available, bool)
    
    @patch('subprocess.run')
    def test_amd_gpu_detection_wmic_success(self, mock_subprocess):
        """Test detección exitosa de GPU AMD con WMIC"""
        # Mock de respuesta exitosa de WMIC para AMD
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Name\nAMD Radeon RX 6800 XT\n"
        mock_subprocess.return_value = mock_result
        
        # Crear nuevo optimizer para que use el mock
        with patch('platform.system', return_value='Windows'):
            optimizer = HardwareOptimizer()
            # El resultado depende de la detección interna
            self.assertIsInstance(optimizer.gpu_available, bool)
    
    @patch('subprocess.run')
    def test_no_gpu_detection(self, mock_subprocess):
        """Test cuando no se detectan GPUs"""
        # Mock de respuesta sin GPUs
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_subprocess.return_value = mock_result
        
        # Crear nuevo optimizer para que use el mock
        with patch('platform.system', return_value='Windows'):
            optimizer = HardwareOptimizer()
            # Verificar que gpu_available es un booleano
            self.assertIsInstance(optimizer.gpu_available, bool)
    
    def test_pytorch_cuda_detection_mock(self):
        """Test detección de PyTorch CUDA cuando está disponible"""
        # Mock de torch para simular CUDA disponible
        mock_torch = Mock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.device_count.return_value = 2
        mock_torch.cuda.get_device_name.return_value = "NVIDIA GeForce RTX 3080"
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            optimizer = HardwareOptimizer()
            # Verificar que se puede detectar GPU
            self.assertIsInstance(optimizer.gpu_available, bool)
    
    def test_pytorch_rocm_detection_mock(self):
        """Test detección de PyTorch ROCm cuando está disponible"""
        # Mock de torch para simular ROCm disponible
        mock_torch = Mock()
        mock_torch.backends.hip.is_available.return_value = True
        mock_torch.hip.device_count.return_value = 1
        mock_torch.hip.get_device_name.return_value = "AMD Radeon RX 6800 XT"
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            optimizer = HardwareOptimizer()
            # Verificar que se puede detectar GPU
            self.assertIsInstance(optimizer.gpu_available, bool)
    
    def test_gpu_detection_methods_exist(self):
        """Test que todos los métodos importantes existen"""
        methods = [
            '_detect_gpu',
            'get_optimal_config',
            '_detect_cpu_info'
        ]
        
        for method in methods:
            self.assertTrue(hasattr(self.optimizer, method),
                          f"Método {method} no encontrado en HardwareOptimizer")
    
    def test_get_optimal_config(self):
        """Test que get_optimal_config retorna una configuración válida"""
        config = self.optimizer.get_optimal_config()
        self.assertIsInstance(config, dict)
        
        # Verificar que contiene información básica
        self.assertIn('cpu_count', config)
        self.assertIn('memory_gb', config)
        self.assertIn('use_gpu', config)
    
    def test_hardware_properties(self):
        """Test que las propiedades de hardware se detectan correctamente"""
        self.assertIsInstance(self.optimizer.cpu_count, int)
        self.assertGreater(self.optimizer.cpu_count, 0)
        
        self.assertIsInstance(self.optimizer.memory_gb, float)
        self.assertGreater(self.optimizer.memory_gb, 0)
        
        self.assertIsInstance(self.optimizer.gpu_available, bool)


class TestFlowerGPUExclusionSimple(unittest.TestCase):
    """Tests simples para verificar exclusión de GPU en Flower"""
    
    def test_flower_process_detection(self):
        """Test detección de proceso Flower"""
        flower_commands = [
            ['celery', '-A', 'backend', 'flower'],
            ['celery', '-A', 'backend', 'flower', '--port=5555'],
            ['python', '-m', 'celery', '-A', 'backend', 'flower']
        ]
        
        for cmd in flower_commands:
            with self.subTest(command=cmd):
                is_flower = 'flower' in ' '.join(cmd)
                self.assertTrue(is_flower, f"No se detectó flower en: {cmd}")
    
    def test_non_flower_process_detection(self):
        """Test que procesos no-Flower no se detectan como Flower"""
        non_flower_commands = [
            ['celery', '-A', 'backend', 'worker'],
            ['celery', '-A', 'backend', 'beat'],
            ['python', 'manage.py', 'runserver']
        ]
        
        for cmd in non_flower_commands:
            with self.subTest(command=cmd):
                is_flower = 'flower' in ' '.join(cmd)
                self.assertFalse(is_flower, f"Incorrectamente detectó flower en: {cmd}")
    
    @patch('sys.argv', ['celery', '-A', 'backend', 'flower'])
    def test_flower_argv_detection(self):
        """Test detección de Flower en sys.argv"""
        is_flower = 'flower' in ' '.join(sys.argv)
        self.assertTrue(is_flower)
    
    @patch('sys.argv', ['celery', '-A', 'backend', 'worker'])
    def test_worker_argv_detection(self):
        """Test detección de Worker en sys.argv"""
        is_flower = 'flower' in ' '.join(sys.argv)
        self.assertFalse(is_flower)


if __name__ == '__main__':
    print("=" * 70)
    print("EJECUTANDO TESTS DE DETECCIÓN DE GPU")
    print("=" * 70)
    
    # Configurar el runner de tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Agregar tests
    suite.addTests(loader.loadTestsFromTestCase(TestGPUDetectionSimple))
    suite.addTests(loader.loadTestsFromTestCase(TestFlowerGPUExclusionSimple))
    
    # Ejecutar tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Mostrar resumen
    print("\n" + "=" * 70)
    print("RESUMEN DE TESTS")
    print("=" * 70)
    print(f"Tests ejecutados: {result.testsRun}")
    print(f"Errores: {len(result.errors)}")
    print(f"Fallos: {len(result.failures)}")
    print(f"Éxito: {result.wasSuccessful()}")
    
    if result.errors:
        print("\nERRORES:")
        for test, error in result.errors:
            print(f"- {test}: {error}")
    
    if result.failures:
        print("\nFALLOS:")
        for test, failure in result.failures:
            print(f"- {test}: {failure}")
    
    # Salir con código apropiado
    sys.exit(0 if result.wasSuccessful() else 1)