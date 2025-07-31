import unittest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from MLPlatformApp.config.hardware_optimization import HardwareOptimizer


class TestGPUDetection(TestCase):
    """Tests para verificar la detección de GPU NVIDIA y AMD"""
    
    def setUp(self):
        """Configuración inicial para los tests"""
        self.optimizer = HardwareOptimizer()
    
    def test_nvidia_gpu_detection_cuml(self):
        """Test detección GPU NVIDIA con cuML/RAPIDS"""
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            # Mock cuML disponible
            with patch.dict('sys.modules', {'cuml': MagicMock()}):
                result = self.optimizer._detect_gpu()
                
                self.assertTrue(result)
                mock_logger.info.assert_called_with("✅ GPU NVIDIA con cuML/RAPIDS detectada")
    
    def test_nvidia_gpu_detection_pytorch_cuda(self):
        """Test detección GPU NVIDIA con PyTorch CUDA"""
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            # Mock PyTorch con CUDA
            mock_torch = MagicMock()
            mock_torch.cuda.is_available.return_value = True
            mock_torch.cuda.device_count.return_value = 1
            mock_torch.cuda.get_device_name.return_value = "NVIDIA GeForce RTX 4080 SUPER"
            
            with patch.dict('sys.modules', {'torch': mock_torch}):
                result = self.optimizer._detect_gpu()
                
                self.assertTrue(result)
                mock_logger.info.assert_called_with(
                    "✅ GPU NVIDIA detectada con PyTorch: NVIDIA GeForce RTX 4080 SUPER (1 dispositivos)"
                )
    
    def test_amd_gpu_detection_pytorch_rocm(self):
        """Test detección GPU AMD con PyTorch ROCm"""
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            # Mock PyTorch con ROCm
            mock_torch = MagicMock()
            mock_torch.cuda.is_available.return_value = False  # CUDA no disponible
            
            # Mock ROCm/HIP
            mock_backends = MagicMock()
            mock_backends.hip.is_available.return_value = True
            mock_torch.backends = mock_backends
            
            mock_hip = MagicMock()
            mock_hip.device_count.return_value = 1
            mock_hip.get_device_name.return_value = "AMD Radeon RX 7900 XTX"
            mock_torch.hip = mock_hip
            
            with patch.dict('sys.modules', {'torch': mock_torch}):
                result = self.optimizer._detect_gpu()
                
                self.assertTrue(result)
                mock_logger.info.assert_called_with(
                    "✅ GPU AMD detectada con PyTorch ROCm: AMD Radeon RX 7900 XTX (1 dispositivos)"
                )
    
    def test_nvidia_gpu_detection_tensorflow(self):
        """Test detección GPU con TensorFlow"""
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            # Mock TensorFlow con GPU
            mock_tf = MagicMock()
            mock_config = MagicMock()
            mock_config.list_physical_devices.return_value = ['GPU:0']
            mock_tf.config = mock_config
            
            with patch.dict('sys.modules', {'tensorflow': mock_tf}):
                result = self.optimizer._detect_gpu()
                
                self.assertTrue(result)
                mock_logger.info.assert_called_with("✅ GPU detectada con TensorFlow: 1 dispositivos")
    
    def test_nvidia_gpu_detection_nvml(self):
        """Test detección GPU NVIDIA con NVML"""
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            # Mock pynvml
            mock_pynvml = MagicMock()
            mock_pynvml.nvmlDeviceGetCount.return_value = 1
            
            mock_handle = MagicMock()
            mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
            mock_pynvml.nvmlDeviceGetName.return_value = b"NVIDIA GeForce RTX 4080 SUPER"
            
            with patch.dict('sys.modules', {'pynvml': mock_pynvml}):
                result = self.optimizer._detect_gpu()
                
                self.assertTrue(result)
                mock_logger.info.assert_called_with("✅ GPU NVIDIA detectada con NVML: 1 dispositivos")
    
    @patch('platform.system')
    @patch('subprocess.run')
    def test_nvidia_gpu_detection_wmic_windows(self, mock_subprocess, mock_platform):
        """Test detección GPU NVIDIA con WMIC en Windows"""
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            # Mock Windows
            mock_platform.return_value = "Windows"
            
            # Mock WMIC output con NVIDIA
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Name\nNVIDIA GeForce RTX 4080 SUPER\n"
            mock_subprocess.return_value = mock_result
            
            result = self.optimizer._detect_gpu()
            
            self.assertTrue(result)
            mock_logger.info.assert_called_with("✅ GPU NVIDIA detectada via Windows WMIC")
    
    @patch('platform.system')
    @patch('subprocess.run')
    def test_amd_gpu_detection_wmic_windows(self, mock_subprocess, mock_platform):
        """Test detección GPU AMD con WMIC en Windows"""
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            # Mock Windows
            mock_platform.return_value = "Windows"
            
            # Mock WMIC output con AMD
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Name\nAMD Radeon RX 7900 XTX\n"
            mock_subprocess.return_value = mock_result
            
            result = self.optimizer._detect_gpu()
            
            self.assertTrue(result)
            mock_logger.info.assert_called_with("✅ GPU AMD detectada via Windows WMIC")
    
    @patch('platform.system')
    @patch('subprocess.run')
    def test_amd_gpu_detection_rocm_smi_linux(self, mock_subprocess, mock_platform):
        """Test detección GPU AMD con rocm-smi en Linux"""
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            # Mock Linux
            mock_platform.return_value = "Linux"
            
            # Mock rocm-smi output
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "GPU[0] : AMD Radeon RX 7900 XTX\n"
            mock_subprocess.return_value = mock_result
            
            result = self.optimizer._detect_gpu()
            
            self.assertTrue(result)
            mock_logger.info.assert_called_with("✅ GPU AMD detectada via rocm-smi")
    
    def test_no_gpu_detection(self):
        """Test cuando no se detecta ninguna GPU"""
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            # Mock todas las librerías como no disponibles
            with patch.dict('sys.modules', {}, clear=True):
                result = self.optimizer._detect_gpu()
                
                self.assertFalse(result)
                mock_logger.info.assert_called_with("❌ No se detectó GPU compatible (NVIDIA o AMD)")
    
    def test_gpu_detection_with_exceptions(self):
        """Test manejo de excepciones durante detección de GPU"""
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            # Mock PyTorch que lanza excepción
            mock_torch = MagicMock()
            mock_torch.cuda.is_available.side_effect = Exception("CUDA error")
            
            with patch.dict('sys.modules', {'torch': mock_torch}):
                result = self.optimizer._detect_gpu()
                
                # Debería continuar con otros métodos y eventualmente retornar False
                self.assertFalse(result)
                mock_logger.warning.assert_called_with("Error al detectar GPU NVIDIA con PyTorch: CUDA error")
    
    def test_system_info_includes_gpu_status(self):
        """Test que la información del sistema incluye el estado de GPU"""
        with patch.object(self.optimizer, '_detect_gpu', return_value=True):
            system_info = self.optimizer.get_system_info()
            
            self.assertIn('gpu_available', system_info)
            self.assertTrue(system_info['gpu_available'])
    
    def test_optimal_config_with_gpu(self):
        """Test configuración óptima cuando hay GPU disponible"""
        with patch.object(self.optimizer, '_detect_gpu', return_value=True):
            config = self.optimizer.get_optimal_config()
            
            self.assertTrue(config['use_gpu'])
            # Con GPU, la concurrencia debería ser conservadora
            self.assertLessEqual(config['recommended_concurrency'], 2)
    
    def test_optimal_config_without_gpu(self):
        """Test configuración óptima cuando no hay GPU disponible"""
        with patch.object(self.optimizer, '_detect_gpu', return_value=False):
            config = self.optimizer.get_optimal_config()
            
            self.assertFalse(config['use_gpu'])
            # Sin GPU, puede usar más concurrencia
            self.assertGreaterEqual(config['recommended_concurrency'], 1)
    
    def test_multiple_gpu_detection_methods(self):
        """Test que se prueban múltiples métodos de detección"""
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            # Mock primer método falla, segundo método funciona
            mock_torch = MagicMock()
            mock_torch.cuda.is_available.return_value = False  # CUDA no disponible
            
            # Mock TensorFlow funciona
            mock_tf = MagicMock()
            mock_config = MagicMock()
            mock_config.list_physical_devices.return_value = ['GPU:0']
            mock_tf.config = mock_config
            
            with patch.dict('sys.modules', {'torch': mock_torch, 'tensorflow': mock_tf}):
                result = self.optimizer._detect_gpu()
                
                self.assertTrue(result)
                # Debería haber intentado PyTorch primero, luego TensorFlow
                mock_logger.info.assert_called_with("✅ GPU detectada con TensorFlow: 1 dispositivos")


class TestGPUDetectionIntegration(TestCase):
    """Tests de integración para detección de GPU"""
    
    def test_hardware_optimizer_initialization(self):
        """Test que HardwareOptimizer se inicializa correctamente"""
        optimizer = HardwareOptimizer()
        
        self.assertIsNotNone(optimizer)
        self.assertTrue(hasattr(optimizer, '_detect_gpu'))
        self.assertTrue(hasattr(optimizer, 'get_optimal_config'))
        self.assertTrue(hasattr(optimizer, 'get_system_info'))
    
    def test_log_system_info_includes_gpu(self):
        """Test que log_system_info incluye información de GPU"""
        optimizer = HardwareOptimizer()
        
        with patch('MLPlatformApp.config.hardware_optimization.logger') as mock_logger:
            optimizer.log_system_info()
            
            # Verificar que se registra información de GPU
            calls = [call.args[0] for call in mock_logger.info.call_args_list]
            gpu_calls = [call for call in calls if 'GPU' in call]
            self.assertGreater(len(gpu_calls), 0)
    
    def test_gpu_detection_affects_model_selection(self):
        """Test que la detección de GPU afecta la selección de modelos"""
        optimizer = HardwareOptimizer()
        
        # Test con GPU
        with patch.object(optimizer, '_detect_gpu', return_value=True):
            config_with_gpu = optimizer.get_optimal_config()
        
        # Test sin GPU
        with patch.object(optimizer, '_detect_gpu', return_value=False):
            config_without_gpu = optimizer.get_optimal_config()
        
        # La configuración debería ser diferente
        self.assertNotEqual(config_with_gpu['use_gpu'], config_without_gpu['use_gpu'])
        self.assertTrue(config_with_gpu['use_gpu'])
        self.assertFalse(config_without_gpu['use_gpu'])


if __name__ == '__main__':
    unittest.main()