import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from celery import Celery
from MLPlatformApp.config.celery_config import get_dynamic_celery_config, get_scaling_recommendation
from MLPlatformApp.config.dynamic_scaling import dynamic_scaler


class TestCeleryIntegration(TestCase):
    """Tests para la integración con Celery"""
    
    def setUp(self):
        """Configuración inicial"""
        self.app = Celery('test')
        self.app.config_from_object('django.conf:settings', namespace='CELERY')
    
    @patch('MLPlatformApp.config.celery_config.dynamic_scaler')
    def test_get_dynamic_celery_config(self, mock_scaler):
        """Test: Obtención de configuración dinámica de Celery"""
        # Mock del scaler
        mock_scaler.calculate_optimal_workers.return_value = (4, {
            'n_jobs': 2,
            'strategy': 'GPU + CPU moderado',
            'system_load': {'cpu_percent': 60.0, 'memory_percent': 55.0}
        })
        
        config = get_dynamic_celery_config()
        
        # Verificar que se obtiene configuración válida
        self.assertIsInstance(config, dict)
        self.assertIn('worker_concurrency', config)
        self.assertIn('worker_prefetch_multiplier', config)
        self.assertIn('task_acks_late', config)
        
        # Verificar valores específicos
        self.assertEqual(config['worker_concurrency'], 4)
        self.assertTrue(config['task_acks_late'])
        self.assertEqual(config['worker_prefetch_multiplier'], 1)
    
    @patch('MLPlatformApp.config.celery_config.dynamic_scaler')
    def test_get_scaling_recommendation_integration(self, mock_scaler):
        """Test: Integración de recomendaciones de escalado"""
        # Mock del scaler
        mock_recommendation = {
            'current_workers': 2,
            'recommended_workers': 4,
            'action': 'scale_up',
            'reason': 'Cola: 8, Carga: 65.0% CPU',
            'config': {
                'strategy': 'GPU + CPU moderado',
                'n_jobs': 2,
                'system_load': {'cpu_percent': 65.0, 'memory_percent': 60.0},
                'safety_applied': False
            }
        }
        
        mock_scaler.get_scaling_recommendation.return_value = mock_recommendation
        
        recommendation = get_scaling_recommendation(current_workers=2, queue_length=8)
        
        # Verificar estructura de la recomendación
        self.assertEqual(recommendation['current_workers'], 2)
        self.assertEqual(recommendation['recommended_workers'], 4)
        self.assertEqual(recommendation['action'], 'scale_up')
        self.assertIn('config', recommendation)
        
        # Verificar que se llamó al scaler correctamente
        mock_scaler.get_scaling_recommendation.assert_called_once_with(2, 8)
    
    @override_settings(CELERY_WORKER_CONCURRENCY=2)
    def test_celery_settings_integration(self):
        """Test: Integración con configuraciones de Django"""
        from django.conf import settings
        
        # Verificar que las configuraciones se pueden leer
        self.assertEqual(settings.CELERY_WORKER_CONCURRENCY, 2)
        
        # Test con configuración dinámica
        with patch('MLPlatformApp.config.celery_config.dynamic_scaler') as mock_scaler:
            # Mock más específico que coincida con el comportamiento real
            mock_scaler.calculate_optimal_workers.return_value = (2, {
                'n_jobs': 2,
                'strategy': 'Test strategy',
                'max_workers': 4,
                'system_load': {'cpu_percent': 60.0, 'memory_percent': 55.0}
            })
            
            config = get_dynamic_celery_config()
            
            # La configuración dinámica debería sobrescribir la estática
            self.assertEqual(config['worker_concurrency'], 2)


class TestWorkerScalingBehavior(TestCase):
    """Tests para el comportamiento de escalado de workers"""
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_worker_scaling_under_load(self, mock_memory, mock_cpu):
        """Test: Escalado de workers bajo carga"""
        # Simular carga creciente
        load_scenarios = [
            (30.0, 40.0, 2),  # Carga baja -> pocos workers
            (60.0, 55.0, 5),  # Carga media -> más workers
            (85.0, 80.0, 8),  # Carga alta -> muchos workers pero limitados por seguridad
        ]
        
        for cpu_load, mem_load, queue_length in load_scenarios:
            mock_cpu.return_value = cpu_load
            mock_memory.return_value = Mock(percent=mem_load, available=8*1024**3)
            
            recommendation = get_scaling_recommendation(
                current_workers=2, 
                queue_length=queue_length
            )
            
            # Verificar que las recomendaciones son coherentes
            self.assertIsInstance(recommendation['recommended_workers'], int)
            self.assertGreater(recommendation['recommended_workers'], 0)
            
            # Con carga alta, debería aplicar límites de seguridad
            if cpu_load > 80 or mem_load > 80:
                config = recommendation['config']
                if 'safety_applied' in config:
                    self.assertTrue(config['safety_applied'], 
                                  f"Deberían aplicarse límites con CPU {cpu_load}%, RAM {mem_load}%")
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_worker_scaling_queue_response(self, mock_memory, mock_cpu):
        """Test: Respuesta del escalado a la longitud de cola"""
        # Mantener carga del sistema constante
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=55.0, available=8*1024**3)
        
        queue_scenarios = [0, 3, 8, 15, 25]
        previous_workers = 0
        
        for queue_length in queue_scenarios:
            recommendation = get_scaling_recommendation(
                current_workers=2, 
                queue_length=queue_length
            )
            
            current_workers = recommendation['recommended_workers']
            
            # Con cola más larga, generalmente debería recomendar más workers
            # (a menos que se apliquen límites de seguridad)
            if queue_length > 0 and not recommendation['config'].get('safety_applied', False):
                if queue_length > 10:  # Cola significativa
                    self.assertGreaterEqual(current_workers, 2, 
                                          f"Cola {queue_length} debería requerir al menos 2 workers")
    
    def test_worker_scaling_consistency(self):
        """Test: Consistencia en las recomendaciones de escalado"""
        # Ejecutar múltiples veces con las mismas condiciones
        with patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent', return_value=60.0):
            with patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory', 
                      return_value=Mock(percent=65.0, available=6*1024**3)):
                
                recommendations = []
                for _ in range(5):
                    rec = get_scaling_recommendation(current_workers=3, queue_length=6)
                    recommendations.append(rec['recommended_workers'])
                
                # Todas las recomendaciones deberían ser iguales
                self.assertEqual(len(set(recommendations)), 1, 
                               "Recomendaciones deberían ser consistentes con mismas condiciones")


class TestCeleryAutoscaleIntegration(TestCase):
    """Tests para la integración con autoscale de Celery"""
    
    def test_autoscale_configuration_format(self):
        """Test: Formato correcto de configuración de autoscale"""
        with patch('MLPlatformApp.config.celery_config.dynamic_scaler') as mock_scaler:
            mock_scaler.calculate_optimal_workers.return_value = (4, {
                'max_workers': 6,
                'n_jobs': 2,
                'strategy': 'GPU + CPU moderado'
            })
            
            config = get_dynamic_celery_config()
            
            # Verificar configuración de autoscale
            self.assertIn('worker_autoscaler', config)
            autoscale_config = config['worker_autoscaler']
            
            # Debería tener formato (max, min)
            self.assertIsInstance(autoscale_config, tuple)
            self.assertEqual(len(autoscale_config), 2)
            
            max_workers, min_workers = autoscale_config
            self.assertGreater(max_workers, 0)
            self.assertGreater(min_workers, 0)
            self.assertGreaterEqual(max_workers, min_workers)
    
    def test_celery_pool_configuration(self):
        """Test: Configuración correcta del pool de Celery"""
        config = get_dynamic_celery_config()
        
        # Verificar configuraciones de pool
        self.assertIn('worker_pool', config)
        self.assertIn('worker_max_tasks_per_child', config)
        self.assertIn('worker_prefetch_multiplier', config)
        
        # Verificar valores apropiados
        self.assertEqual(config['worker_pool'], 'solo')
        self.assertGreater(config['worker_max_tasks_per_child'], 0)
        self.assertEqual(config['worker_prefetch_multiplier'], 1)
    
    @patch('MLPlatformApp.config.celery_config.dynamic_scaler')
    def test_resource_limits_integration(self, mock_scaler):
        """Test: Integración con límites de recursos"""
        # Simular sistema con recursos limitados
        mock_scaler.calculate_optimal_workers.return_value = (2, {
            'max_workers': 3,
            'n_jobs': 1,
            'strategy': 'CPU conservador',
            'system_load': {'cpu_percent': 75.0, 'memory_percent': 70.0},
            'safety_applied': True
        })
        
        config = get_dynamic_celery_config()
        
        # Con recursos limitados, debería ser más conservador
        self.assertLessEqual(config['worker_concurrency'], 3)
        
        # Verificar que se aplicaron límites
        autoscale_max, autoscale_min = config['worker_autoscaler']
        self.assertLessEqual(autoscale_max, 3)


class TestCeleryTaskExecution(TestCase):
    """Tests para la ejecución de tareas con escalado dinámico"""
    
    def test_task_routing_configuration(self):
        """Test: Configuración de enrutamiento de tareas"""
        config = get_dynamic_celery_config()
        
        # Verificar configuración de colas
        self.assertIn('task_routes', config)
        
        # Verificar que las tareas de entrenamiento van a la cola correcta
        routes = config['task_routes']
        if 'MLPlatformApp.training.train_model_task' in routes:
            self.assertEqual(routes['MLPlatformApp.training.train_model_task'], 
                           {'queue': 'training'})
    
    @patch('MLPlatformApp.config.celery_config.dynamic_scaler')
    def test_task_execution_under_scaling(self, mock_scaler):
        """Test: Ejecución de tareas durante escalado"""
        # Simular diferentes estados de escalado
        scaling_states = [
            (1, 'scale_down', 'Sistema sobrecargado'),
            (3, 'maintain', 'Sistema estable'),
            (5, 'scale_up', 'Cola larga')
        ]
        
        for workers, action, reason in scaling_states:
            mock_scaler.get_scaling_recommendation.return_value = {
                'recommended_workers': workers,
                'action': action,
                'reason': reason,
                'config': {
                    'n_jobs': min(2, workers),
                    'strategy': 'Test strategy'
                }
            }
            
            config = get_dynamic_celery_config()
            
            # Verificar que la configuración es válida para cualquier estado
            self.assertGreater(config['worker_concurrency'], 0)
            self.assertIsInstance(config['worker_autoscaler'], tuple)
    
    def test_error_handling_in_scaling(self):
        """Test: Manejo de errores durante el escalado"""
        # Simular error en el scaler
        with patch('MLPlatformApp.config.celery_config.dynamic_scaler') as mock_scaler:
            mock_scaler.calculate_optimal_workers.side_effect = Exception("Test error")
            
            # Debería devolver configuración por defecto sin fallar
            try:
                config = get_dynamic_celery_config()
                
                # Verificar que se devuelve configuración válida
                self.assertIsInstance(config, dict)
                self.assertIn('worker_concurrency', config)
                
            except Exception as e:
                self.fail(f"get_dynamic_celery_config no debería fallar: {e}")


class TestScalingMetrics(TestCase):
    """Tests para métricas de escalado"""
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_metrics_collection_accuracy(self, mock_memory, mock_cpu):
        """Test: Precisión en la recolección de métricas"""
        # Configurar valores específicos
        mock_cpu.return_value = 67.5
        mock_memory.return_value = Mock(
            percent=72.3, 
            available=5.5*1024**3
        )
        
        # Obtener métricas del sistema
        system_load = dynamic_scaler.get_current_system_load()
        
        # Verificar precisión
        self.assertEqual(system_load['cpu_percent'], 67.5)
        self.assertEqual(system_load['memory_percent'], 72.3)
        self.assertAlmostEqual(system_load['memory_available_gb'], 5.5, places=1)
    
    def test_metrics_consistency_over_time(self):
        """Test: Consistencia de métricas a lo largo del tiempo"""
        with patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent') as mock_cpu:
            with patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory') as mock_memory:
                
                # Simular métricas estables
                mock_cpu.return_value = 55.0
                mock_memory.return_value = Mock(percent=60.0, available=6*1024**3)
                
                metrics_over_time = []
                for _ in range(10):
                    metrics = dynamic_scaler.get_current_system_load()
                    metrics_over_time.append(metrics)
                    time.sleep(0.01)  # Pequeña pausa
                
                # Verificar consistencia
                cpu_values = [m['cpu_percent'] for m in metrics_over_time]
                memory_values = [m['memory_percent'] for m in metrics_over_time]
                
                self.assertEqual(len(set(cpu_values)), 1, "CPU debería ser consistente")
                self.assertEqual(len(set(memory_values)), 1, "Memoria debería ser consistente")


if __name__ == '__main__':
    unittest.main()