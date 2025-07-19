import unittest
import time
from unittest.mock import Mock, patch, MagicMock, call
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO
from MLPlatformApp.management.commands.start_dynamic_scaling import Command


class TestScalingMonitorCommand(TestCase):
    """Tests para el comando de monitoreo de escalado"""
    
    def setUp(self):
        """Configuración inicial"""
        self.command = Command()
        self.command.stdout = StringIO()
        self.command.style = Mock()
        self.command.style.SUCCESS = lambda x: f"SUCCESS: {x}"
        self.command.style.WARNING = lambda x: f"WARNING: {x}"
        self.command.style.ERROR = lambda x: f"ERROR: {x}"
        self.command.style.HTTP_INFO = lambda x: f"INFO: {x}"
    
    def test_command_arguments_parsing(self):
        """Test: Parsing correcto de argumentos del comando"""
        # Test argumentos por defecto
        parser = self.command.create_parser('test', 'start_dynamic_scaling')
        options = parser.parse_args([])
        
        self.assertEqual(options.interval, 30)
        self.assertEqual(options.immediate_check_interval, 5)
        self.assertEqual(options.critical_cpu_threshold, 85.0)
        self.assertEqual(options.critical_memory_threshold, 85.0)
        self.assertEqual(options.spike_threshold, 20.0)
        self.assertFalse(options.dry_run)
        self.assertFalse(options.verbose)
        
        # Test argumentos personalizados
        custom_args = [
            '--interval', '60',
            '--immediate-check-interval', '10',
            '--critical-cpu-threshold', '90.0',
            '--critical-memory-threshold', '90.0',
            '--spike-threshold', '25.0',
            '--dry-run',
            '--verbose',
            '--cpu-threshold', '75.0',
            '--memory-threshold', '75.0'
        ]
        options = parser.parse_args(custom_args)
        
        self.assertEqual(options.interval, 60)
        self.assertEqual(options.immediate_check_interval, 10)
        self.assertEqual(options.critical_cpu_threshold, 90.0)
        self.assertEqual(options.critical_memory_threshold, 90.0)
        self.assertEqual(options.spike_threshold, 25.0)
        self.assertTrue(options.dry_run)
        self.assertTrue(options.verbose)
        self.assertEqual(options.cpu_threshold, 75.0)
        self.assertEqual(options.memory_threshold, 75.0)
    
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.virtual_memory')
    def test_immediate_trigger_detection(self, mock_memory, mock_cpu):
        """Test: Detección correcta de triggers inmediatos"""
        mock_cpu.return_value = 90.0  # CPU crítico
        mock_memory.return_value = Mock(percent=70.0)
        
        current_time = time.time()
        
        should_trigger, cpu_hist, mem_hist = self.command._should_trigger_immediate_check(
            current_time=current_time,
            last_immediate_check=0,
            immediate_check_interval=5,
            critical_cpu_threshold=85.0,
            critical_memory_threshold=85.0,
            spike_threshold=20.0,
            cpu_history=[],
            memory_history=[],
            max_history_size=5
        )
        
        self.assertTrue(should_trigger, "Debería detectar trigger crítico de CPU")
        self.assertEqual(len(cpu_hist), 1, "Debería actualizar historial de CPU")
        self.assertEqual(len(mem_hist), 1, "Debería actualizar historial de memoria")
    
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.virtual_memory')
    def test_spike_detection_algorithm(self, mock_memory, mock_cpu):
        """Test: Algoritmo de detección de picos"""
        mock_cpu.return_value = 80.0  # Pico de CPU
        mock_memory.return_value = Mock(percent=55.0)
        
        # Historial con valores bajos
        cpu_history = [45.0, 50.0, 48.0]
        memory_history = [40.0, 45.0, 42.0]
        
        current_time = time.time()
        
        should_trigger, _, _ = self.command._should_trigger_immediate_check(
            current_time=current_time,
            last_immediate_check=0,
            immediate_check_interval=5,
            critical_cpu_threshold=85.0,
            critical_memory_threshold=85.0,
            spike_threshold=20.0,  # 80 - 48 = 32 > 20
            cpu_history=cpu_history,
            memory_history=memory_history,
            max_history_size=5
        )
        
        self.assertTrue(should_trigger, "Debería detectar pico de CPU")
    
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.virtual_memory')
    def test_history_management(self, mock_memory, mock_cpu):
        """Test: Gestión correcta del historial de métricas"""
        mock_cpu.return_value = 60.0
        mock_memory.return_value = Mock(percent=55.0)
        
        # Historial lleno
        cpu_history = [50.0, 52.0, 54.0, 56.0, 58.0]  # 5 elementos
        memory_history = [45.0, 47.0, 49.0, 51.0, 53.0]  # 5 elementos
        
        current_time = time.time()
        
        _, new_cpu_hist, new_mem_hist = self.command._should_trigger_immediate_check(
            current_time=current_time,
            last_immediate_check=0,
            immediate_check_interval=5,
            critical_cpu_threshold=85.0,
            critical_memory_threshold=85.0,
            spike_threshold=20.0,
            cpu_history=cpu_history,
            memory_history=memory_history,
            max_history_size=5
        )
        
        # Debería mantener el tamaño máximo
        self.assertEqual(len(new_cpu_hist), 5, "Historial CPU debería mantener tamaño máximo")
        self.assertEqual(len(new_mem_hist), 5, "Historial memoria debería mantener tamaño máximo")
        
        # Debería tener el nuevo valor al final
        self.assertEqual(new_cpu_hist[-1], 60.0, "Nuevo valor CPU debería estar al final")
        self.assertEqual(new_mem_hist[-1], 55.0, "Nuevo valor memoria debería estar al final")
        
        # El primer valor debería haber sido removido
        self.assertNotEqual(new_cpu_hist[0], 50.0, "Primer valor CPU debería haber sido removido")
    
    def test_system_status_classification(self):
        """Test: Clasificación correcta del estado del sistema"""
        # Test estado normal
        status = self.command._get_system_status(50.0, 60.0, 80.0, 80.0)
        self.assertEqual(status, 'normal')
        
        # Test carga alta
        status = self.command._get_system_status(70.0, 70.0, 80.0, 80.0)
        self.assertEqual(status, 'high_load')
        
        # Test sobrecarga
        status = self.command._get_system_status(85.0, 75.0, 80.0, 80.0)
        self.assertEqual(status, 'overloaded')
        
        # Test carga baja
        status = self.command._get_system_status(25.0, 25.0, 80.0, 80.0)
        self.assertEqual(status, 'low_load')
    
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.get_scaling_recommendation')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.virtual_memory')
    def test_monitor_and_scale_dry_run(self, mock_memory, mock_cpu, mock_get_recommendation):
        """Test: Modo dry-run no aplica cambios"""
        mock_cpu.return_value = 75.0
        mock_memory.return_value = Mock(percent=70.0)
        
        mock_get_recommendation.return_value = {
            'action': 'scale_up',
            'reason': 'Test scaling up',
            'recommended_workers': 4,
            'current_workers': 2,
            'recommended_config': 'Test config'
        }
        
        # Mock del método _apply_scaling
        with patch.object(self.command, '_apply_scaling') as mock_apply:
            self.command._monitor_and_scale(
                dry_run=True,
                verbose=True,
                cpu_threshold=80.0,
                memory_threshold=80.0
            )
            
            # En dry-run no debería aplicar escalado
            mock_apply.assert_not_called()
    
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.get_scaling_recommendation')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.virtual_memory')
    def test_monitor_and_scale_active_mode(self, mock_memory, mock_cpu, mock_get_recommendation):
        """Test: Modo activo aplica cambios"""
        mock_cpu.return_value = 75.0
        mock_memory.return_value = Mock(percent=70.0)
        
        mock_get_recommendation.return_value = {
            'action': 'scale_up',
            'reason': 'Test scaling up',
            'recommended_workers': 4,
            'current_workers': 2,
            'recommended_config': 'Test config'
        }
        
        # Mock del método _apply_scaling
        with patch.object(self.command, '_apply_scaling') as mock_apply:
            self.command._monitor_and_scale(
                dry_run=False,
                verbose=True,
                cpu_threshold=80.0,
                memory_threshold=80.0
            )
            
            # En modo activo debería aplicar escalado
            mock_apply.assert_called_once()
    
    def test_queue_length_simulation(self):
        """Test: Simulación de longitud de cola"""
        with patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.cpu_percent') as mock_cpu:
            # CPU alta debería simular cola larga
            mock_cpu.return_value = 80.0
            queue_length = self.command._get_queue_length()
            self.assertGreater(queue_length, 0, "CPU alta debería simular cola")
            
            # CPU baja debería simular cola vacía
            mock_cpu.return_value = 30.0
            queue_length = self.command._get_queue_length()
            self.assertEqual(queue_length, 0, "CPU baja debería simular cola vacía")


class TestScalingMonitorIntegration(TestCase):
    """Tests de integración para el monitor de escalado"""
    
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.time.sleep')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.virtual_memory')
    def test_monitoring_loop_interruption(self, mock_memory, mock_cpu, mock_sleep):
        """Test: Interrupción correcta del loop de monitoreo"""
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0)
        
        # Simular KeyboardInterrupt después de algunas iteraciones
        mock_sleep.side_effect = [None, None, KeyboardInterrupt()]
        
        command = Command()
        command.stdout = StringIO()
        command.style = Mock()
        command.style.SUCCESS = lambda x: f"SUCCESS: {x}"
        command.style.WARNING = lambda x: f"WARNING: {x}"
        command.style.ERROR = lambda x: f"ERROR: {x}"
        command.style.HTTP_INFO = lambda x: f"INFO: {x}"
        command.style.WARNING = lambda x: f"WARNING: {x}"
        command.style.ERROR = lambda x: f"ERROR: {x}"
        command.style.HTTP_INFO = lambda x: f"INFO: {x}"
        
        # El comando debería manejar la interrupción gracefully
        try:
            command.handle(
                interval=1,
                immediate_check_interval=1,
                critical_cpu_threshold=85.0,
                critical_memory_threshold=85.0,
                spike_threshold=20.0,
                dry_run=True,
                verbose=False,
                cpu_threshold=80.0,
                memory_threshold=80.0
            )
        except KeyboardInterrupt:
            self.fail("KeyboardInterrupt no debería propagarse")
    
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.os.environ')
    def test_environment_variable_setting(self, mock_environ):
        """Test: Configuración correcta de variables de entorno"""
        command = Command()
        command.stdout = StringIO()
        command.style = Mock()
        command.style.SUCCESS = lambda x: f"SUCCESS: {x}"
        command.style.WARNING = lambda x: f"WARNING: {x}"
        command.style.ERROR = lambda x: f"ERROR: {x}"
        command.style.HTTP_INFO = lambda x: f"INFO: {x}"
        
        # Mock para evitar el loop infinito
        with patch('MLPlatformApp.management.commands.start_dynamic_scaling.time.sleep', 
                  side_effect=KeyboardInterrupt()):
            try:
                command.handle(
                    interval=30,
                    immediate_check_interval=5,
                    critical_cpu_threshold=85.0,
                    critical_memory_threshold=85.0,
                    spike_threshold=20.0,
                    dry_run=True,
                    verbose=False,
                    cpu_threshold=75.0,
                    memory_threshold=75.0
                )
            except KeyboardInterrupt:
                pass
        
        # Verificar que se configuraron las variables de entorno
        mock_environ.__setitem__.assert_any_call('CPU_THRESHOLD', '75.0')
        mock_environ.__setitem__.assert_any_call('MEMORY_THRESHOLD', '75.0')
    
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.logger')
    def test_error_handling_and_logging(self, mock_logger):
        """Test: Manejo de errores y logging"""
        command = Command()
        command.stdout = StringIO()
        command.style = Mock()
        command.style.SUCCESS = lambda x: f"SUCCESS: {x}"
        command.style.WARNING = lambda x: f"WARNING: {x}"
        command.style.ERROR = lambda x: f"ERROR: {x}"
        command.style.HTTP_INFO = lambda x: f"INFO: {x}"
        
        # Simular error en _monitor_and_scale
        with patch.object(command, '_monitor_and_scale', side_effect=Exception("Test error")):
            with patch('MLPlatformApp.management.commands.start_dynamic_scaling.time.sleep', 
                      side_effect=KeyboardInterrupt()):
                try:
                    command.handle(
                        interval=1,
                        immediate_check_interval=1,
                        critical_cpu_threshold=85.0,
                        critical_memory_threshold=85.0,
                        spike_threshold=20.0,
                        dry_run=True,
                        verbose=False,
                        cpu_threshold=80.0,
                        memory_threshold=80.0
                    )
                except KeyboardInterrupt:
                    pass
        
        # Verificar que se logueó el error
        mock_logger.error.assert_called()


class TestScalingPerformance(TestCase):
    """Tests de rendimiento para el sistema de escalado"""
    
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.virtual_memory')
    def test_monitoring_performance(self, mock_memory, mock_cpu):
        """Test: Rendimiento del monitoreo"""
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0)
        
        command = Command()
        
        # Medir tiempo de ejecución de una iteración de monitoreo
        start_time = time.time()
        
        command._monitor_and_scale(
            dry_run=True,
            verbose=False,
            cpu_threshold=80.0,
            memory_threshold=80.0
        )
        
        execution_time = time.time() - start_time
        
        # El monitoreo debería ser rápido (< 1 segundo)
        self.assertLess(execution_time, 1.0, 
                       "Monitoreo debería ejecutarse en menos de 1 segundo")
    
    def test_trigger_check_performance(self):
        """Test: Rendimiento de la verificación de triggers"""
        command = Command()
        
        # Historial grande para test de rendimiento
        cpu_history = [50.0] * 100
        memory_history = [60.0] * 100
        
        with patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.cpu_percent', return_value=55.0):
            with patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.virtual_memory', 
                      return_value=Mock(percent=65.0)):
                
                start_time = time.time()
                
                command._should_trigger_immediate_check(
                    current_time=time.time(),
                    last_immediate_check=0,
                    immediate_check_interval=5,
                    critical_cpu_threshold=85.0,
                    critical_memory_threshold=85.0,
                    spike_threshold=20.0,
                    cpu_history=cpu_history,
                    memory_history=memory_history,
                    max_history_size=5
                )
                
                execution_time = time.time() - start_time
                
                # La verificación de triggers debería ser muy rápida
                self.assertLess(execution_time, 0.1, 
                               "Verificación de triggers debería ser muy rápida")


if __name__ == '__main__':
    unittest.main()