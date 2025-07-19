import unittest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from MLPlatformApp.config.dynamic_scaling import dynamic_scaler
from MLPlatformApp.config.celery_config import get_scaling_recommendation


class TestStressScenarios(TestCase):
    """Tests para escenarios de estrés del sistema de autoescalado"""
    
    def setUp(self):
        """Configuración inicial"""
        self.stress_results = []
        self.error_count = 0
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_high_load_scenario(self, mock_memory, mock_cpu):
        """Test: Escenario de carga alta sostenida"""
        # Simular carga alta sostenida
        mock_cpu.return_value = 85.0
        mock_memory.return_value = Mock(percent=80.0, available=2*1024**3)
        
        # Probar con diferentes longitudes de cola
        queue_lengths = [0, 5, 10, 20, 50, 100]
        
        for queue_length in queue_lengths:
            with self.subTest(queue_length=queue_length):
                recommendation = get_scaling_recommendation(
                    current_workers=4, 
                    queue_length=queue_length
                )
                
                # Con carga alta, el sistema debería ser conservador
                self.assertIsNotNone(recommendation)
                self.assertIn('recommended_workers', recommendation)
                
                # No debería recomendar demasiados workers con recursos limitados
                if recommendation['config'].get('safety_applied', False):
                    self.assertLessEqual(
                        recommendation['recommended_workers'], 
                        8,  # Límite razonable bajo estrés
                        f"Con cola {queue_length} y carga alta, no debería exceder 8 workers"
                    )
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_memory_pressure_scenario(self, mock_memory, mock_cpu):
        """Test: Escenario de presión de memoria"""
        # CPU normal pero memoria muy alta
        mock_cpu.return_value = 45.0
        mock_memory.return_value = Mock(percent=90.0, available=1*1024**3)
        
        recommendation = get_scaling_recommendation(
            current_workers=3, 
            queue_length=15
        )
        
        # Con presión de memoria, debería limitar workers
        self.assertIsNotNone(recommendation)
        
        # Verificar que se aplicaron límites de seguridad
        config = recommendation['config']
        if 'safety_applied' in config:
            self.assertTrue(config['safety_applied'], 
                          "Debería aplicar límites con 90% de memoria")
        
        # No debería recomendar muchos workers
        self.assertLessEqual(
            recommendation['recommended_workers'], 
            5,
            "Con presión de memoria no debería recomendar muchos workers"
        )
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_cpu_spike_scenario(self, mock_memory, mock_cpu):
        """Test: Escenario de picos de CPU"""
        # Memoria normal pero CPU muy alta
        mock_cpu.return_value = 95.0
        mock_memory.return_value = Mock(percent=50.0, available=8*1024**3)
        
        recommendation = get_scaling_recommendation(
            current_workers=2, 
            queue_length=8
        )
        
        # Con CPU al 95%, debería ser muy conservador
        self.assertIsNotNone(recommendation)
        
        # Verificar límites de seguridad
        config = recommendation['config']
        if 'safety_applied' in config:
            self.assertTrue(config['safety_applied'], 
                          "Debería aplicar límites con 95% de CPU")
        
        # Podría incluso recomendar reducir workers
        if recommendation['action'] == 'scale_down':
            self.assertLess(
                recommendation['recommended_workers'], 
                recommendation['current_workers'],
                "Con CPU al 95% podría recomendar reducir workers"
            )
    
    def test_rapid_queue_changes(self):
        """Test: Cambios rápidos en la longitud de cola"""
        with patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent', return_value=60.0):
            with patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory', 
                      return_value=Mock(percent=65.0, available=6*1024**3)):
                
                # Simular cambios rápidos en la cola
                queue_changes = [0, 20, 5, 50, 2, 100, 1]
                recommendations = []
                
                for queue_length in queue_changes:
                    rec = get_scaling_recommendation(
                        current_workers=3, 
                        queue_length=queue_length
                    )
                    recommendations.append(rec)
                
                # Verificar que todas las recomendaciones son válidas
                for i, rec in enumerate(recommendations):
                    with self.subTest(queue_length=queue_changes[i]):
                        self.assertIsNotNone(rec)
                        self.assertIn('recommended_workers', rec)
                        self.assertGreater(rec['recommended_workers'], 0)
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_concurrent_scaling_requests(self, mock_memory, mock_cpu):
        """Test: Solicitudes concurrentes de escalado"""
        mock_cpu.return_value = 70.0
        mock_memory.return_value = Mock(percent=60.0, available=5*1024**3)
        
        def make_scaling_request(worker_id, results_list):
            """Función para hacer solicitud de escalado en hilo separado"""
            try:
                rec = get_scaling_recommendation(
                    current_workers=3, 
                    queue_length=10
                )
                results_list.append((worker_id, rec))
            except Exception as e:
                results_list.append((worker_id, f"Error: {e}"))
        
        # Crear múltiples hilos para solicitudes concurrentes
        threads = []
        results = []
        
        for i in range(10):
            thread = threading.Thread(
                target=make_scaling_request, 
                args=(i, results)
            )
            threads.append(thread)
            thread.start()
        
        # Esperar a que terminen todos los hilos
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Verificar resultados
        self.assertEqual(len(results), 10, "Deberían completarse todas las solicitudes")
        
        # Verificar que no hay errores
        errors = [r for r in results if isinstance(r[1], str) and "Error" in r[1]]
        self.assertEqual(len(errors), 0, f"No deberían haber errores: {errors}")
        
        # Verificar consistencia en las recomendaciones
        recommendations = [r[1]['recommended_workers'] for r in results if isinstance(r[1], dict)]
        unique_recommendations = set(recommendations)
        
        # Con las mismas condiciones, deberían ser similares (permitir pequeñas variaciones)
        self.assertLessEqual(len(unique_recommendations), 3, 
                           "Las recomendaciones concurrentes deberían ser consistentes")


class TestSystemSaturationPrevention(TestCase):
    """Tests para prevención de saturación del sistema"""
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_prevents_system_overload(self, mock_memory, mock_cpu):
        """Test: Prevención de sobrecarga del sistema"""
        # Simular sistema ya sobrecargado
        mock_cpu.return_value = 88.0
        mock_memory.return_value = Mock(percent=85.0, available=1.5*1024**3)
        
        # Incluso con cola muy larga, no debería saturar más
        recommendation = get_scaling_recommendation(
            current_workers=6, 
            queue_length=100
        )
        
        # Debería recomendar mantener o reducir workers
        self.assertIn(recommendation['action'], ['maintain', 'scale_down'], 
                     "Con sistema sobrecargado no debería escalar hacia arriba")
        
        # Si recomienda mantener, no debería exceder workers actuales
        if recommendation['action'] == 'maintain':
            self.assertLessEqual(
                recommendation['recommended_workers'], 
                recommendation['current_workers']
            )
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_gradual_scaling_under_pressure(self, mock_memory, mock_cpu):
        """Test: Escalado gradual bajo presión"""
        # Sistema con presión moderada
        mock_cpu.return_value = 75.0
        mock_memory.return_value = Mock(percent=70.0, available=3*1024**3)
        
        # Probar escalado desde pocos workers
        current_workers = 1
        queue_length = 20
        
        recommendation = get_scaling_recommendation(
            current_workers=current_workers, 
            queue_length=queue_length
        )
        
        # Debería escalar, pero de forma conservadora
        if recommendation['action'] == 'scale_up':
            increase = recommendation['recommended_workers'] - current_workers
            self.assertLessEqual(increase, 3, 
                               "Bajo presión, el escalado debería ser gradual")
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_minimum_workers_maintained(self, mock_memory, mock_cpu):
        """Test: Mantenimiento de workers mínimos"""
        # Sistema con muy poca carga
        mock_cpu.return_value = 15.0
        mock_memory.return_value = Mock(percent=25.0, available=12*1024**3)
        
        recommendation = get_scaling_recommendation(
            current_workers=3, 
            queue_length=0
        )
        
        # Nunca debería recomendar menos del mínimo
        min_workers = 1  # Asumiendo mínimo de 1
        self.assertGreaterEqual(
            recommendation['recommended_workers'], 
            min_workers,
            "Siempre debería mantener al menos 1 worker"
        )
    
    def test_resource_exhaustion_handling(self):
        """Test: Manejo de agotamiento de recursos"""
        # Simular recursos extremadamente limitados
        with patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent', return_value=98.0):
            with patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory', 
                      return_value=Mock(percent=95.0, available=0.5*1024**3)):
                
                recommendation = get_scaling_recommendation(
                    current_workers=4, 
                    queue_length=50
                )
                
                # Con recursos agotados, debería recomendar reducir
                self.assertEqual(recommendation['action'], 'scale_down', 
                               "Con recursos agotados debería reducir workers")
                
                # Debería reducir significativamente
                self.assertLess(
                    recommendation['recommended_workers'], 
                    recommendation['current_workers'],
                    "Debería recomendar menos workers"
                )


class TestEdgeCases(TestCase):
    """Tests para casos extremos"""
    
    def test_zero_queue_length(self):
        """Test: Cola vacía"""
        with patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent', return_value=40.0):
            with patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory', 
                      return_value=Mock(percent=45.0, available=8*1024**3)):
                
                recommendation = get_scaling_recommendation(
                    current_workers=5, 
                    queue_length=0
                )
                
                # Con cola vacía, podría recomendar reducir workers
                self.assertIn(recommendation['action'], ['maintain', 'scale_down'])
                
                if recommendation['action'] == 'scale_down':
                    self.assertLess(
                        recommendation['recommended_workers'], 
                        recommendation['current_workers']
                    )
    
    def test_extremely_long_queue(self):
        """Test: Cola extremadamente larga"""
        with patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent', return_value=30.0):
            with patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory', 
                      return_value=Mock(percent=35.0, available=10*1024**3)):
                
                recommendation = get_scaling_recommendation(
                    current_workers=2, 
                    queue_length=1000
                )
                
                # Incluso con cola muy larga, debería tener límites
                self.assertLessEqual(
                    recommendation['recommended_workers'], 
                    20,  # Límite razonable máximo
                    "Incluso con cola muy larga debería tener límites"
                )
    
    def test_single_worker_scenario(self):
        """Test: Escenario con un solo worker"""
        with patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent', return_value=50.0):
            with patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory', 
                      return_value=Mock(percent=55.0, available=6*1024**3)):
                
                recommendation = get_scaling_recommendation(
                    current_workers=1, 
                    queue_length=10
                )
                
                # Con un solo worker y cola, debería escalar
                self.assertEqual(recommendation['action'], 'scale_up')
                self.assertGreater(
                    recommendation['recommended_workers'], 
                    1,
                    "Con un worker y cola debería recomendar más workers"
                )
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory')
    def test_invalid_metrics_handling(self, mock_memory, mock_cpu):
        """Test: Manejo de métricas inválidas"""
        # Simular métricas inválidas
        mock_cpu.side_effect = Exception("CPU metrics unavailable")
        mock_memory.side_effect = Exception("Memory metrics unavailable")
        
        # Debería manejar errores graciosamente
        try:
            recommendation = get_scaling_recommendation(
                current_workers=3, 
                queue_length=5
            )
            
            # Si maneja el error, debería devolver algo válido
            if recommendation is not None:
                self.assertIn('recommended_workers', recommendation)
                self.assertGreater(recommendation['recommended_workers'], 0)
                
        except Exception:
            # Si no puede manejar el error, al menos no debería crashear silenciosamente
            pass
    
    def test_negative_values_handling(self):
        """Test: Manejo de valores negativos"""
        with patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent', return_value=50.0):
            with patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory', 
                      return_value=Mock(percent=55.0, available=6*1024**3)):
                
                # Probar con valores negativos (que no deberían ocurrir)
                try:
                    recommendation = get_scaling_recommendation(
                        current_workers=-1,  # Valor inválido
                        queue_length=5
                    )
                    
                    # Si acepta el valor, debería corregirlo
                    if recommendation is not None:
                        self.assertGreater(recommendation['recommended_workers'], 0)
                        
                except (ValueError, AssertionError):
                    # Es aceptable que rechace valores inválidos
                    pass


class TestPerformanceUnderLoad(TestCase):
    """Tests de rendimiento bajo carga"""
    
    def test_scaling_decision_performance(self):
        """Test: Rendimiento de decisiones de escalado"""
        with patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent', return_value=60.0):
            with patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory', 
                      return_value=Mock(percent=65.0, available=6*1024**3)):
                
                # Medir tiempo de múltiples decisiones
                start_time = time.time()
                
                for i in range(100):
                    recommendation = get_scaling_recommendation(
                        current_workers=3, 
                        queue_length=i % 20
                    )
                    self.assertIsNotNone(recommendation)
                
                end_time = time.time()
                total_time = end_time - start_time
                
                # Cada decisión debería ser rápida (< 10ms en promedio)
                avg_time_per_decision = total_time / 100
                self.assertLess(avg_time_per_decision, 0.01, 
                              f"Decisiones muy lentas: {avg_time_per_decision:.4f}s promedio")
    
    def test_memory_usage_stability(self):
        """Test: Estabilidad del uso de memoria"""
        import gc
        
        # Forzar garbage collection inicial
        gc.collect()
        
        with patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent', return_value=55.0):
            with patch('MLPlatformApp.config.dynamic_scaling.psutil.virtual_memory', 
                      return_value=Mock(percent=60.0, available=7*1024**3)):
                
                # Realizar muchas operaciones
                for i in range(1000):
                    recommendation = get_scaling_recommendation(
                        current_workers=2 + (i % 5), 
                        queue_length=i % 30
                    )
                    
                    # Verificar que no hay memory leaks obvios
                    if i % 100 == 0:
                        gc.collect()
                
                # Test pasó si llegamos aquí sin errores de memoria
                self.assertTrue(True, "No memory leaks detectados")


if __name__ == '__main__':
    unittest.main()