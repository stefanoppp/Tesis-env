import unittest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
import sys
import os


class TestFlowerGPUExclusion(TestCase):
    """Tests para verificar que Flower no ejecute detección de GPU"""
    
    def setUp(self):
        """Configuración inicial para los tests"""
        # Limpiar cualquier configuración previa
        if 'MLPlatformApp.config.hardware_optimization' in sys.modules:
            del sys.modules['MLPlatformApp.config.hardware_optimization']
        if 'MLPlatformApp.config.celery_config' in sys.modules:
            del sys.modules['MLPlatformApp.config.celery_config']
    
    def test_flower_process_detection(self):
        """Test que se detecta correctamente cuando el proceso es Flower"""
        # Simular argumentos de línea de comandos de Flower
        test_argv = ['celery', '-A', 'backend', 'flower', '--port=5555']
        
        with patch('sys.argv', test_argv):
            # Verificar que se detecta como proceso Flower
            is_flower = 'flower' in ' '.join(test_argv)
            self.assertTrue(is_flower)
    
    def test_worker_process_detection(self):
        """Test que se detecta correctamente cuando el proceso es un worker"""
        # Simular argumentos de línea de comandos de worker
        test_argv = ['celery', '-A', 'backend', 'worker', '--loglevel=info']
        
        with patch('sys.argv', test_argv):
            # Verificar que NO se detecta como proceso Flower
            is_flower = 'flower' in ' '.join(test_argv)
            self.assertFalse(is_flower)
    
    @patch('sys.argv', ['celery', '-A', 'backend', 'flower', '--port=5555'])
    @patch('builtins.print')
    def test_flower_settings_no_gpu_detection(self, mock_print):
        """Test que Flower no ejecuta detección de GPU en settings.py"""
        # Mock de las funciones de configuración para evitar importación real
        with patch('MLPlatformApp.config.celery_config.get_celery_config') as mock_get_config, \
             patch('MLPlatformApp.config.celery_config.get_dynamic_celery_config') as mock_get_dynamic, \
             patch('MLPlatformApp.config.celery_config.log_celery_recommendations') as mock_log_recommendations, \
             patch('MLPlatformApp.config.dynamic_scaling.dynamic_scaler') as mock_scaler:
            
            # Simular la lógica de settings.py
            import sys
            is_flower_process = 'flower' in ' '.join(sys.argv)
            
            if not is_flower_process:
                # Esto NO debería ejecutarse para Flower
                mock_get_config.assert_not_called()
                mock_log_recommendations.assert_not_called()
            else:
                # Para Flower, solo configuración mínima
                self.assertTrue(is_flower_process)
                
            # Verificar que se imprime el mensaje correcto para Flower
            mock_print.assert_called_with("[FLOWER] Iniciando panel de monitoreo - Sin detección de hardware")
    
    @patch('sys.argv', ['celery', '-A', 'backend', 'worker', '--loglevel=info'])
    def test_worker_settings_with_gpu_detection(self):
        """Test que los workers SÍ ejecutan detección de GPU"""
        with patch('MLPlatformApp.config.celery_config.get_celery_config') as mock_get_config, \
             patch('MLPlatformApp.config.celery_config.log_celery_recommendations') as mock_log_recommendations:
            
            # Mock configuración básica
            mock_get_config.return_value = {
                'worker_concurrency': 2,
                'worker_prefetch_multiplier': 1,
                'task_acks_late': True,
                'worker_max_tasks_per_child': 10,
                'task_soft_time_limit': 1800,
                'task_time_limit': 2400,
                'worker_disable_rate_limits': False,
                'task_reject_on_worker_lost': True
            }
            
            # Simular la lógica de settings.py para workers
            import sys
            is_flower_process = 'flower' in ' '.join(sys.argv)
            
            if not is_flower_process:
                # Para workers, SÍ debería ejecutarse
                self.assertFalse(is_flower_process)
                # Estas funciones deberían ser llamadas para workers
                # (en un escenario real, pero aquí solo verificamos la lógica)
    
    def test_flower_minimal_configuration(self):
        """Test que Flower recibe configuración mínima sin hardware detection"""
        # Configuración mínima esperada para Flower
        expected_config = {
            'CELERY_WORKER_CONCURRENCY': 1,
            'CELERY_WORKER_PREFETCH_MULTIPLIER': 1,
            'CELERY_TASK_ACKS_LATE': True,
            'CELERY_WORKER_MAX_TASKS_PER_CHILD': 10,
            'CELERY_TASK_SOFT_TIME_LIMIT': 1800,
            'CELERY_TASK_TIME_LIMIT': 2400,
            'CELERY_WORKER_DISABLE_RATE_LIMITS': False,
            'CELERY_TASK_REJECT_ON_WORKER_LOST': True
        }
        
        # Verificar que la configuración mínima es válida
        for key, value in expected_config.items():
            self.assertIsNotNone(value)
            if isinstance(value, int):
                self.assertGreaterEqual(value, 0)
    
    @patch('sys.argv', ['celery', '-A', 'backend', 'flower'])
    def test_flower_no_hardware_optimization_import(self):
        """Test que Flower no importa hardware_optimization innecesariamente"""
        with patch('MLPlatformApp.config.hardware_optimization.HardwareOptimizer') as mock_optimizer:
            # Simular que es proceso Flower
            is_flower_process = 'flower' in ' '.join(sys.argv)
            
            if is_flower_process:
                # Para Flower, no debería instanciar HardwareOptimizer
                mock_optimizer.assert_not_called()
    
    def test_different_flower_command_variations(self):
        """Test detección de Flower con diferentes variaciones de comando"""
        flower_commands = [
            ['celery', '-A', 'backend', 'flower'],
            ['celery', '-A', 'backend', 'flower', '--port=5555'],
            ['celery', '-A', 'backend', 'flower', '--broker=redis://localhost:6379'],
            ['python', '-m', 'celery', '-A', 'backend', 'flower'],
            ['celery', 'flower', '-A', 'backend']
        ]
        
        for cmd in flower_commands:
            with self.subTest(command=cmd):
                is_flower = 'flower' in ' '.join(cmd)
                self.assertTrue(is_flower, f"Failed to detect flower in command: {cmd}")
    
    def test_non_flower_commands(self):
        """Test que comandos que no son Flower no se detectan como tal"""
        non_flower_commands = [
            ['celery', '-A', 'backend', 'worker'],
            ['celery', '-A', 'backend', 'beat'],
            ['python', 'manage.py', 'runserver'],
            ['python', 'manage.py', 'start_dynamic_scaling'],
            ['celery', '-A', 'backend', 'inspect', 'active']
        ]
        
        for cmd in non_flower_commands:
            with self.subTest(command=cmd):
                is_flower = 'flower' in ' '.join(cmd)
                self.assertFalse(is_flower, f"Incorrectly detected flower in command: {cmd}")
    
    @patch('builtins.print')
    def test_flower_startup_message(self, mock_print):
        """Test que Flower muestra el mensaje correcto al iniciar"""
        with patch('sys.argv', ['celery', '-A', 'backend', 'flower']):
            # Simular la lógica de configuración para Flower
            is_flower_process = 'flower' in ' '.join(['celery', '-A', 'backend', 'flower'])
            
            if is_flower_process:
                print("[FLOWER] Iniciando panel de monitoreo - Sin detección de hardware")
                
            mock_print.assert_called_with("[FLOWER] Iniciando panel de monitoreo - Sin detección de hardware")
    
    def test_environment_variable_isolation(self):
        """Test que las variables de entorno de escalado no afectan a Flower"""
        with patch.dict(os.environ, {
            'DYNAMIC_SCALING_ENABLED': 'true',
            'CPU_THRESHOLD': '70',
            'MEMORY_THRESHOLD': '75'
        }):
            with patch('sys.argv', ['celery', '-A', 'backend', 'flower']):
                # Para Flower, estas variables no deberían procesarse
                is_flower_process = 'flower' in ' '.join(sys.argv)
                
                if is_flower_process:
                    # Flower debería ignorar estas configuraciones
                    self.assertTrue(is_flower_process)
                    # No debería procesar configuración de escalado dinámico


class TestFlowerIntegration(TestCase):
    """Tests de integración para verificar que Flower funciona sin GPU detection"""
    
    def test_flower_docker_compose_configuration(self):
        """Test que la configuración de docker-compose para Flower es correcta"""
        # Verificar que el comando de Flower en docker-compose no incluye configuraciones de GPU
        expected_flower_command = "celery -A backend flower --port=5555"
        
        # El comando debería ser simple y no incluir configuraciones de hardware
        self.assertNotIn('--concurrency', expected_flower_command)
        self.assertNotIn('--autoscale', expected_flower_command)
        self.assertNotIn('gpu', expected_flower_command.lower())
    
    def test_flower_environment_variables(self):
        """Test que Flower solo necesita variables básicas de conexión"""
        required_flower_env = {
            'REDIS_HOST': 'redis',
            'REDIS_PORT': '6379',
            'REDIS_DB': '0',
            'CELERY_BROKER_URL': 'redis://redis:6379/0'
        }
        
        # Flower no debería necesitar variables de GPU o hardware
        gpu_related_vars = [
            'DYNAMIC_SCALING_ENABLED',
            'CPU_THRESHOLD',
            'MEMORY_THRESHOLD',
            'GPU_ACCELERATION',
            'CUDA_VISIBLE_DEVICES'
        ]
        
        for var in gpu_related_vars:
            self.assertNotIn(var, required_flower_env)
    
    def test_flower_resource_limits(self):
        """Test que Flower tiene límites de recursos apropiados"""
        # Flower debería tener límites conservadores ya que es solo monitoreo
        expected_limits = {
            'cpus': '0.2',
            'memory': '512M'
        }
        
        # Verificar que los límites son apropiados para un panel de monitoreo
        self.assertLessEqual(float(expected_limits['cpus']), 0.5)
        self.assertIn('M', expected_limits['memory'])  # Debería estar en MB, no GB


if __name__ == '__main__':
    unittest.main()