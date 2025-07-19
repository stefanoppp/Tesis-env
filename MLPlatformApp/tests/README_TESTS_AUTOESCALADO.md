# Pruebas del Sistema de Autoescalado Dinámico

Este directorio contiene una suite completa de pruebas para el sistema de autoescalado dinámico de workers de Celery.

## 📁 Estructura de Pruebas

### Archivos de Pruebas

1. **`test_autoscaling.py`** - Pruebas principales del sistema de autoescalado
   - `TestDynamicScalingPolicy`: Pruebas de la política de escalado
   - `TestAutoScalingTriggers`: Pruebas de triggers de autoescalado
   - `TestSystemSaturationPrevention`: Pruebas de prevención de saturación
   - `TestIntegrationScaling`: Pruebas de integración completa

2. **`test_scaling_monitor.py`** - Pruebas del comando de monitoreo
   - `TestScalingMonitorCommand`: Pruebas del comando Django
   - `TestMonitoringTriggers`: Pruebas de triggers de monitoreo
   - `TestMonitoringMetrics`: Pruebas de recolección de métricas
   - `TestMonitoringBehavior`: Pruebas de comportamiento del monitor
   - `TestMonitoringConfiguration`: Pruebas de configuración
   - `TestMonitoringErrorHandling`: Pruebas de manejo de errores
   - `TestMonitoringPerformance`: Pruebas de rendimiento

3. **`test_celery_integration.py`** - Pruebas de integración con Celery
   - `TestCeleryIntegration`: Integración básica con Celery
   - `TestWorkerScalingBehavior`: Comportamiento de escalado de workers
   - `TestCeleryAutoscaleIntegration`: Integración con autoscale de Celery
   - `TestCeleryTaskExecution`: Ejecución de tareas con escalado
   - `TestScalingMetrics`: Métricas de escalado

4. **`test_stress_scenarios.py`** - Pruebas de estrés y casos extremos
   - `TestStressScenarios`: Escenarios de alta carga
   - `TestSystemSaturationPrevention`: Prevención de saturación bajo estrés
   - `TestEdgeCases`: Casos extremos y límites
   - `TestPerformanceUnderLoad`: Rendimiento bajo carga

5. **`test_autoscaling_suite.py`** - Suite organizadora de todas las pruebas
   - `AutoscalingTestSuite`: Suite principal
   - Funciones para ejecutar subconjuntos de pruebas
   - Runner personalizado con reportes

## 🚀 Cómo Ejecutar las Pruebas

### Ejecutar Todas las Pruebas

```bash
# Usando Django test runner
python manage.py test MLPlatformApp.tests.test_autoscaling_suite

# O ejecutar la suite directamente
python MLPlatformApp/tests/test_autoscaling_suite.py
```

### Ejecutar Pruebas Específicas

#### Pruebas Rápidas (solo las más importantes)
```bash
python MLPlatformApp/tests/test_autoscaling_suite.py --quick
```

#### Pruebas de Estrés
```bash
python MLPlatformApp/tests/test_autoscaling_suite.py --stress
```

#### Pruebas de Integración
```bash
python MLPlatformApp/tests/test_autoscaling_suite.py --integration
```

#### Pruebas con Salida Verbosa
```bash
python MLPlatformApp/tests/test_autoscaling_suite.py --verbose
```

### Ejecutar Archivos Individuales

```bash
# Pruebas principales de autoescalado
python manage.py test MLPlatformApp.tests.test_autoscaling

# Pruebas del monitor de escalado
python manage.py test MLPlatformApp.tests.test_scaling_monitor

# Pruebas de integración con Celery
python manage.py test MLPlatformApp.tests.test_celery_integration

# Pruebas de estrés
python manage.py test MLPlatformApp.tests.test_stress_scenarios
```

### Ejecutar Clases de Pruebas Específicas

```bash
# Solo pruebas de política de escalado
python manage.py test MLPlatformApp.tests.test_autoscaling.TestDynamicScalingPolicy

# Solo pruebas de triggers
python manage.py test MLPlatformApp.tests.test_autoscaling.TestAutoScalingTriggers

# Solo pruebas de prevención de saturación
python manage.py test MLPlatformApp.tests.test_autoscaling.TestSystemSaturationPrevention
```

### Ejecutar Pruebas Individuales

```bash
# Prueba específica de escalado hacia arriba
python manage.py test MLPlatformApp.tests.test_autoscaling.TestDynamicScalingPolicy.test_scale_up_with_long_queue

# Prueba específica de triggers críticos
python manage.py test MLPlatformApp.tests.test_autoscaling.TestAutoScalingTriggers.test_immediate_trigger_on_critical_cpu
```

## 📊 Cobertura de Pruebas

### Funcionalidades Probadas

#### ✅ Política de Escalado Dinámico
- [x] Escalado hacia arriba con cola larga
- [x] Escalado hacia abajo con CPU alta
- [x] Prevención de sobrecarga por límites de seguridad
- [x] Configuración para sistemas sin GPU
- [x] Recomendaciones de escalado coherentes

#### ✅ Triggers de Autoescalado
- [x] Triggers inmediatos por CPU crítico
- [x] Detección de picos súbitos de carga
- [x] No-trigger en condiciones normales
- [x] Prevención de spam de triggers

#### ✅ Prevención de Saturación
- [x] Prevención de escalado en umbrales críticos
- [x] Escalado conservador cerca de límites
- [x] Cumplimiento de mínimo de workers
- [x] Manejo de recursos agotados

#### ✅ Integración con Celery
- [x] Configuración dinámica de Celery
- [x] Integración con autoscale de Celery
- [x] Enrutamiento de tareas
- [x] Configuración de pools de workers
- [x] Manejo de errores en escalado

#### ✅ Monitoreo y Comandos
- [x] Parsing de argumentos del comando
- [x] Detección de triggers inmediatos
- [x] Gestión de historial de métricas
- [x] Clasificación de estado del sistema
- [x] Modo dry-run vs activo
- [x] Simulación de longitud de cola

#### ✅ Escenarios de Estrés
- [x] Carga alta sostenida
- [x] Presión de memoria
- [x] Picos de CPU
- [x] Cambios rápidos en cola
- [x] Solicitudes concurrentes
- [x] Casos extremos (cola vacía, cola muy larga)
- [x] Valores inválidos

#### ✅ Rendimiento
- [x] Tiempo de respuesta de decisiones
- [x] Estabilidad de uso de memoria
- [x] Consistencia bajo carga
- [x] Escalabilidad de monitoreo

## 🔧 Configuración de Pruebas

### Variables de Entorno para Pruebas

```bash
# Configurar para pruebas
export DJANGO_SETTINGS_MODULE=MLPlatformApp.settings.test
export CELERY_ALWAYS_EAGER=True
export CELERY_EAGER_PROPAGATES_EXCEPTIONS=True
```

### Dependencias para Pruebas

Las pruebas utilizan mocking extensivo para simular:
- Métricas del sistema (CPU, memoria)
- Longitud de cola de Celery
- Configuraciones de hardware
- Condiciones de error

### Configuración de Base de Datos para Pruebas

```python
# En settings/test.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
```

## 📈 Interpretación de Resultados

### Salida Exitosa
```
✅ ¡TODAS LAS PRUEBAS PASARON!
Pruebas ejecutadas: 150
Errores: 0
Fallos: 0
Omitidas: 0
```

### Salida con Errores
```
❌ Algunas pruebas fallaron.
Pruebas ejecutadas: 150
Errores: 2
Fallos: 1
Omitidas: 0

❌ ERRORES:
  - test_scaling_under_pressure: ImportError: No module named 'psutil'

❌ FALLOS:
  - test_worker_scaling_consistency: AssertionError: Expected 4 workers, got 3
```

## 🐛 Solución de Problemas

### Errores Comunes

#### ImportError: No module named 'psutil'
```bash
pip install psutil
```

#### ImportError: No module named 'celery'
```bash
pip install celery
```

#### Django settings not configured
```bash
export DJANGO_SETTINGS_MODULE=MLPlatformApp.settings
```

#### Pruebas lentas
- Usar `--quick` para ejecutar solo pruebas esenciales
- Verificar que no hay procesos de fondo consumiendo recursos

#### Fallos intermitentes
- Pueden deberse a condiciones de carrera en pruebas concurrentes
- Ejecutar pruebas individualmente para aislar problemas

### Debugging

#### Ejecutar con Debug
```bash
python manage.py test MLPlatformApp.tests.test_autoscaling --debug-mode
```

#### Ver Logs Detallados
```bash
python manage.py test MLPlatformApp.tests.test_autoscaling --verbosity=3
```

#### Ejecutar Solo Pruebas Fallidas
```bash
python manage.py test MLPlatformApp.tests.test_autoscaling --failfast
```

## 📝 Agregar Nuevas Pruebas

### Estructura de Nueva Prueba

```python
class TestNuevaFuncionalidad(TestCase):
    """Tests para nueva funcionalidad"""
    
    def setUp(self):
        """Configuración inicial"""
        pass
    
    @patch('MLPlatformApp.config.dynamic_scaling.psutil.cpu_percent')
    def test_nueva_funcionalidad(self, mock_cpu):
        """Test: Descripción de lo que prueba"""
        # Configurar mocks
        mock_cpu.return_value = 50.0
        
        # Ejecutar funcionalidad
        resultado = funcion_a_probar()
        
        # Verificar resultado
        self.assertEqual(resultado, valor_esperado)
```

### Agregar a la Suite

1. Importar la nueva clase en `test_autoscaling_suite.py`
2. Agregar a `create_test_suite()`
3. Actualizar documentación

## 🎯 Mejores Prácticas

### Para Escribir Pruebas
- Usar mocking para dependencias externas
- Probar casos límite y errores
- Mantener pruebas independientes
- Usar nombres descriptivos
- Documentar qué se está probando

### Para Ejecutar Pruebas
- Ejecutar pruebas rápidas durante desarrollo
- Ejecutar suite completa antes de commits
- Usar pruebas de estrés para validación final
- Monitorear tiempo de ejecución

### Para Mantener Pruebas
- Actualizar pruebas cuando cambie funcionalidad
- Revisar y limpiar pruebas obsoletas
- Mantener cobertura alta
- Documentar cambios en pruebas

---

**Nota**: Estas pruebas están diseñadas para validar el comportamiento del sistema de autoescalado en diferentes condiciones y garantizar que funcione correctamente en producción.