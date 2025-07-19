import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from MLPlatformApp.config.dynamic_scaling import DynamicScalingPolicy, dynamic_scaler
from MLPlatformApp.config.celery_config import get_scaling_recommendation


class TestDynamicScalingPolicy(TestCase):
    """Tests para la política de escalado dinámico"""
    
    def setUp(self):
        """Configuración inicial para cada test"""
        self.scaler = DynamicScalingPolicy()
        # Mock del hardware config para tests consistentes
        self.scaler.hardware_config = {
            'use_gpu': True,
            'physical_cpu_count': 8,
            'memory_gb': 16,
            'recommended_concurrency': 4
        }
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_scale_up_high_queue_length(self, mock_memory, mock_cpu):
        """Test: Escalado hacia arriba con cola larga"""
        # Simular sistema con carga normal pero cola larga
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0, available=8*1024**3)
        
        # Cola larga debería triggear escalado
        optimal_workers, config = self.scaler.calculate_optimal_workers(queue_length=12)
        
        # Verificar que se recomienda más workers
        self.assertGreater(optimal_workers, 2, "Debería recomendar más workers con cola larga")
        self.assertEqual(config['strategy'], 'GPU + CPU moderado')
        self.assertGreater(config['queue_factor'], 10)
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_scale_down_high_cpu_usage(self, mock_memory, mock_cpu):
        """Test: Escalado hacia abajo con CPU alta"""
        # Simular sistema sobrecargado
        mock_cpu.return_value = 85.0
        mock_memory.return_value = Mock(percent=75.0, available=4*1024**3)
        
        # Sistema sobrecargado debería reducir workers
        optimal_workers, config = self.scaler.calculate_optimal_workers(queue_length=3)
        
        # Verificar que se aplican límites de seguridad
        self.assertTrue(config['safety_applied'], "Deberían aplicarse límites de seguridad")
        self.assertLessEqual(optimal_workers, 2, "Debería reducir workers con CPU alta")
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_safety_limits_prevent_overload(self, mock_memory, mock_cpu):
        """Test: Límites de seguridad previenen saturación"""
        # Simular sistema al límite
        mock_cpu.return_value = 82.0
        mock_memory.return_value = Mock(percent=83.0, available=2*1024**3)
        
        # Incluso con cola larga, no debería escalar si el sistema está al límite
        optimal_workers, config = self.scaler.calculate_optimal_workers(queue_length=15)
        
        # Verificar que los límites de seguridad se aplican
        self.assertTrue(config['safety_applied'], "Límites de seguridad deberían aplicarse")
        self.assertLessEqual(optimal_workers, self.scaler.min_workers + 1, 
                           "No debería escalar con sistema sobrecargado")
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_cpu_only_configuration(self, mock_memory, mock_cpu):
        """Test: Configuración para sistemas sin GPU"""
        # Configurar sistema sin GPU
        self.scaler.hardware_config['use_gpu'] = False
        self.scaler.hardware_config['memory_gb'] = 8
        
        mock_cpu.return_value = 45.0
        mock_memory.return_value = Mock(percent=50.0, available=4*1024**3)
        
        optimal_workers, config = self.scaler.calculate_optimal_workers(queue_length=5)
        
        # Verificar configuración más conservadora sin GPU
        self.assertEqual(config['strategy'], 'CPU conservador')
        self.assertLessEqual(optimal_workers, 4, "Configuración CPU debería ser más conservadora")
        self.assertLessEqual(config['n_jobs'], 2, "n_jobs debería ser menor sin GPU")
    
    def test_scaling_recommendation_actions(self):
        """Test: Recomendaciones de escalado correctas"""
        with patch.object(self.scaler, 'calculate_optimal_workers') as mock_calc:
            # Test scale_up
            mock_calc.return_value = (4, {
                'system_load': {'cpu_percent': 65.0, 'memory_percent': 60.0},
                'queue_factor': 8,
                'safety_applied': False
            })
            
            recommendation = self.scaler.get_scaling_recommendation(current_workers=2, queue_length=8)
            
            self.assertEqual(recommendation['action'], 'scale_up')
            self.assertEqual(recommendation['current_workers'], 2)
            self.assertEqual(recommendation['recommended_workers'], 4)
            self.assertIn('Cola:', recommendation['reason'])
            
            # Test scale_down
            mock_calc.return_value = (1, {
                'system_load': {'cpu_percent': 85.0, 'memory_percent': 80.0},
                'queue_factor': 2,
                'safety_applied': True
            })
            
            recommendation = self.scaler.get_scaling_recommendation(current_workers=3, queue_length=2)
            
            self.assertEqual(recommendation['action'], 'scale_down')
            self.assertEqual(recommendation['current_workers'], 3)
            self.assertEqual(recommendation['recommended_workers'], 1)
            self.assertIn('Sobrecarga:', recommendation['reason'])
            
            # Test maintain
            mock_calc.return_value = (2, {
                'system_load': {'cpu_percent': 45.0, 'memory_percent': 50.0},
                'queue_factor': 3,
                'safety_applied': False
            })
            
            recommendation = self.scaler.get_scaling_recommendation(current_workers=2, queue_length=3)
            
            self.assertEqual(recommendation['action'], 'maintain')
            self.assertEqual(recommendation['reason'], 'Sistema estable')


class TestAutoScalingTriggers(TestCase):
    """Tests para triggers de autoescalado"""
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_immediate_trigger_critical_cpu(self, mock_memory, mock_cpu):
        """Test: Trigger inmediato por CPU crítico"""
        mock_cpu.return_value = 90.0  # CPU crítico
        mock_memory.return_value = Mock(percent=70.0)
        
        # Simular el comportamiento del comando de monitoreo
        from MLPlatformApp.management.commands.start_dynamic_scaling import Command
        command = Command()
        
        # Test del método de trigger inmediato
        should_trigger, _, _ = command._should_trigger_immediate_check(
            current_time=time.time(),
            last_immediate_check=0,
            immediate_check_interval=5,
            critical_cpu_threshold=85.0,
            critical_memory_threshold=85.0,
            spike_threshold=20.0,
            cpu_history=[],
            memory_history=[],
            max_history_size=5
        )
        
        self.assertTrue(should_trigger, "Debería triggear con CPU crítico")
    
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.virtual_memory')
    def test_spike_detection_trigger(self, mock_memory, mock_cpu):
        """Test: Trigger por pico súbito de carga"""
        mock_cpu.return_value = 75.0  # Pico de CPU
        mock_memory.return_value = Mock(percent=60.0)
        
        from MLPlatformApp.management.commands.start_dynamic_scaling import Command
        command = Command()
        command.stdout = Mock()
        command.style = Mock()
        command.style.ERROR = lambda x: f"ERROR: {x}"
        command.style.WARNING = lambda x: f"WARNING: {x}"
        
        # Historial con carga baja previa
        cpu_history = [45.0, 50.0, 48.0]
        memory_history = [40.0, 45.0, 42.0]
        
        should_trigger, _, _ = command._should_trigger_immediate_check(
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
        
        self.assertTrue(should_trigger, "Debería triggear por pico súbito de CPU")
    
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.management.commands.start_dynamic_scaling.psutil.virtual_memory')
    def test_no_trigger_normal_conditions(self, mock_memory, mock_cpu):
        """Test: No trigger en condiciones normales"""
        mock_cpu.return_value = 55.0  # CPU normal
        mock_memory.return_value = Mock(percent=60.0)
        
        from MLPlatformApp.management.commands.start_dynamic_scaling import Command
        command = Command()
        command.stdout = Mock()
        command.style = Mock()
        command.style.ERROR = lambda x: f"ERROR: {x}"
        command.style.WARNING = lambda x: f"WARNING: {x}"
        
        # Historial con carga estable
        cpu_history = [50.0, 52.0, 54.0]
        memory_history = [58.0, 60.0, 59.0]
        
        should_trigger, _, _ = command._should_trigger_immediate_check(
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
        
        self.assertFalse(should_trigger, "No debería triggear en condiciones normales")
    
    def test_trigger_cooldown_prevention(self):
        """Test: Prevención de spam de triggers"""
        from MLPlatformApp.management.commands.start_dynamic_scaling import Command
        command = Command()
        
        current_time = time.time()
        last_check = current_time - 2  # Hace 2 segundos
        
        # Debería prevenir trigger si no ha pasado suficiente tiempo
        should_trigger, _, _ = command._should_trigger_immediate_check(
            current_time=current_time,
            last_immediate_check=last_check,
            immediate_check_interval=5,  # Requiere 5 segundos
            critical_cpu_threshold=85.0,
            critical_memory_threshold=85.0,
            spike_threshold=20.0,
            cpu_history=[],
            memory_history=[],
            max_history_size=5
        )
        
        self.assertFalse(should_trigger, "Debería prevenir spam de triggers")


class TestSystemSaturationPrevention(TestCase):
    """Tests para prevención de saturación del sistema"""
    
    def setUp(self):
        self.scaler = DynamicScalingPolicy()
        self.scaler.hardware_config = {
            'use_gpu': True,
            'physical_cpu_count': 4,
            'memory_gb': 8,
            'recommended_concurrency': 2
        }
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_prevent_scaling_at_cpu_threshold(self, mock_memory, mock_cpu):
        """Test: Prevenir escalado cuando CPU está en el umbral"""
        mock_cpu.return_value = 80.0  # En el umbral
        mock_memory.return_value = Mock(percent=70.0, available=4*1024**3)
        
        system_load = self.scaler.get_current_system_load()
        
        # Intentar escalar con sistema al límite
        final_workers = self.scaler._apply_safety_limits(4, system_load)
        
        # Debería reducir workers por seguridad
        self.assertLess(final_workers, 4, "Debería reducir workers en el umbral de CPU")
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_prevent_scaling_at_memory_threshold(self, mock_memory, mock_cpu):
        """Test: Prevenir escalado cuando memoria está en el umbral"""
        mock_cpu.return_value = 60.0
        mock_memory.return_value = Mock(percent=80.0, available=2*1024**3)  # En el umbral
        
        system_load = self.scaler.get_current_system_load()
        
        # Intentar escalar con memoria al límite
        final_workers = self.scaler._apply_safety_limits(4, system_load)
        
        # Debería reducir workers por seguridad
        self.assertLess(final_workers, 4, "Debería reducir workers en el umbral de memoria")
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_conservative_scaling_near_limits(self, mock_memory, mock_cpu):
        """Test: Escalado conservador cerca de los límites"""
        mock_cpu.return_value = 75.0  # Cerca del límite
        mock_memory.return_value = Mock(percent=75.0, available=3*1024**3)
        
        system_load = self.scaler.get_current_system_load()
        
        # Debería ser conservador cerca de los límites
        final_workers = self.scaler._apply_safety_limits(6, system_load)
        
        # No debería exceder la concurrencia recomendada
        self.assertLessEqual(final_workers, self.scaler.hardware_config['recommended_concurrency'],
                           "Debería ser conservador cerca de los límites")
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_minimum_workers_enforcement(self, mock_memory, mock_cpu):
        """Test: Enforcement del mínimo de workers"""
        mock_cpu.return_value = 95.0  # Sistema muy sobrecargado
        mock_memory.return_value = Mock(percent=90.0, available=1*1024**3)
        
        system_load = self.scaler.get_current_system_load()
        
        # Incluso con sistema sobrecargado, mantener mínimo
        final_workers = self.scaler._apply_safety_limits(1, system_load)
        
        # Nunca debería ir por debajo del mínimo
        self.assertGreaterEqual(final_workers, self.scaler.min_workers,
                              "Debería mantener el mínimo de workers")


class TestIntegrationScaling(TestCase):
    """Tests de integración para el sistema completo"""
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_end_to_end_scaling_scenario(self, mock_memory, mock_cpu):
        """Test: Escenario completo de escalado"""
        # Escenario: Sistema normal con cola creciente
        mock_cpu.return_value = 55.0
        mock_memory.return_value = Mock(percent=60.0, available=6*1024**3)
        
        # Obtener recomendación inicial
        recommendation = get_scaling_recommendation(current_workers=2, queue_length=8)
        
        # Verificar que se recomienda escalado
        self.assertIn(recommendation['action'], ['scale_up', 'maintain'])
        self.assertIsInstance(recommendation['recommended_workers'], int)
        self.assertGreater(recommendation['recommended_workers'], 0)
        
        # Verificar que la configuración es coherente
        config = recommendation['config']
        self.assertIn('system_load', config)
        self.assertIn('strategy', config)
        self.assertIn('queue_factor', config)
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_stress_scenario_handling(self, mock_memory, mock_cpu):
        """Test: Manejo de escenario de estrés"""
        # Escenario: Sistema sobrecargado con cola larga
        mock_cpu.return_value = 88.0
        mock_memory.return_value = Mock(percent=85.0, available=1*1024**3)
        
        recommendation = get_scaling_recommendation(current_workers=4, queue_length=15)
        
        # En estrés, debería priorizar estabilidad sobre rendimiento
        self.assertIn(recommendation['action'], ['scale_down', 'maintain'])
        
        # Verificar que se aplicaron límites de seguridad
        config = recommendation['config']
        if 'safety_applied' in config:
            self.assertTrue(config['safety_applied'], "Deberían aplicarse límites de seguridad")
    
    def test_logging_functionality(self):
        """Test: Funcionalidad de logging"""
        scaler = DynamicScalingPolicy()
        
        # Mock recommendation
        recommendation = {
            'current_workers': 2,
            'recommended_workers': 3,
            'action': 'scale_up',
            'reason': 'Test reason',
            'config': {
                'strategy': 'Test strategy',
                'system_load': {'cpu_percent': 65.0, 'memory_percent': 60.0},
                'queue_factor': 8,
                'n_jobs': 2,
                'safety_applied': False
            }
        }
        
        # Verificar que el logging no falla
        try:
            scaler.log_scaling_decision(recommendation)
        except Exception as e:
            self.fail(f"Logging falló: {e}")


if __name__ == '__main__':
    unittest.main()