# Tests de Detección de GPU y Exclusión de Flower

Este documento describe los tests implementados para verificar el correcto funcionamiento de la detección de GPU y la exclusión de logs de Flower.

## Archivos de Test

### 1. `test_gpu_detection.py`
Tests completos para la detección de GPU con dependencias de Django.

**Características:**
- Tests unitarios para detección de GPUs NVIDIA y AMD
- Tests de integración con diferentes métodos de detección
- Verificación de configuración del sistema basada en hardware
- Tests de manejo de excepciones

### 2. `test_flower_gpu_exclusion.py`
Tests específicos para verificar que Flower no ejecute detección de GPU.

**Características:**
- Verificación de detección de procesos Flower
- Tests de configuración mínima para Flower
- Verificación de exclusión de hardware optimization
- Tests de integración con Docker Compose

### 3. `simple_gpu_test.py` (Test Independiente)
Tests simplificados que no requieren Django ni dependencias externas.

**Características:**
- Tests básicos de funcionalidad sin dependencias
- Mocks de librerías externas (PyTorch, TensorFlow, etc.)
- Verificación de métodos de detección de hardware
- Tests de exclusión de Flower

## Métodos de Detección de GPU Testeados

### NVIDIA GPUs
1. **cuML (RAPIDS)** - Para computación científica acelerada
2. **PyTorch CUDA** - Framework de deep learning
3. **TensorFlow** - Framework de machine learning
4. **NVML (nvidia-ml-py)** - NVIDIA Management Library
5. **WMIC (Windows)** - Comando de sistema Windows

### AMD GPUs
1. **PyTorch ROCm** - Framework de deep learning para AMD
2. **TensorFlow ROCm** - Framework de machine learning para AMD
3. **WMIC (Windows)** - Detección de tarjetas AMD/Radeon
4. **rocm-smi (Linux)** - Herramienta de sistema ROCm

## Exclusión de Flower

### Problema Resuelto
Antes de la implementación, Flower ejecutaba detección de hardware innecesariamente, generando logs confusos ya que Flower es solo un panel de monitoreo.

### Solución Implementada
1. **Detección de Proceso**: Se detecta si el proceso actual es Flower mediante `sys.argv`
2. **Configuración Mínima**: Flower recibe configuración básica sin detección de hardware
3. **Logs Específicos**: Flower muestra mensaje específico de inicio sin logs de GPU

### Configuración para Flower
```python
# Configuración mínima para Flower
if 'flower' in ' '.join(sys.argv):
    print("[FLOWER] Iniciando panel de monitoreo - Sin detección de hardware")
    # Aplicar configuración mínima
else:
    # Configuración completa con detección de hardware
```

## Ejecución de Tests

### Tests Completos (Requiere Django)
```bash
python manage.py test MLPlatformApp.tests.test_gpu_detection
python manage.py test MLPlatformApp.tests.test_flower_gpu_exclusion
```

### Tests Independientes (Sin Django)
```bash
python simple_gpu_test.py
```

### Tests con pytest (Si está instalado)
```bash
pytest MLPlatformApp/tests/test_gpu_detection.py -v
pytest MLPlatformApp/tests/test_flower_gpu_exclusion.py -v
```

## Resultados Esperados

### Tests de GPU Detection
- ✅ Detección correcta de GPUs NVIDIA cuando están disponibles
- ✅ Detección correcta de GPUs AMD cuando están disponibles
- ✅ Manejo apropiado cuando no hay GPUs disponibles
- ✅ Configuración del sistema basada en hardware detectado
- ✅ Manejo de excepciones en métodos de detección

### Tests de Flower Exclusion
- ✅ Detección correcta de procesos Flower
- ✅ No ejecución de detección de hardware en Flower
- ✅ Configuración mínima aplicada a Flower
- ✅ Logs específicos para Flower
- ✅ Funcionamiento normal para workers y otros procesos

## Beneficios de la Implementación

1. **Mejor Experiencia de Usuario**: Logs más claros y relevantes
2. **Optimización de Recursos**: Flower no ejecuta detección innecesaria
3. **Compatibilidad Ampliada**: Soporte para GPUs NVIDIA y AMD
4. **Robustez**: Tests exhaustivos garantizan funcionamiento correcto
5. **Mantenibilidad**: Código bien documentado y testeado

## Configuración de Hardware Soportada

### GPUs NVIDIA
- CUDA 11.x y 12.x
- Drivers NVIDIA actualizados
- PyTorch con soporte CUDA
- TensorFlow-GPU
- cuML/RAPIDS (opcional)

### GPUs AMD
- ROCm 5.x
- Drivers AMD actualizados
- PyTorch con soporte ROCm
- TensorFlow-ROCm (opcional)

### Sistemas Operativos
- Windows 10/11 (WMIC para detección)
- Linux (rocm-smi para AMD, nvidia-smi para NVIDIA)
- macOS (detección limitada)

## Troubleshooting

### Error: "No module named 'torch'"
```bash
pip install torch
# Para NVIDIA:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
# Para AMD:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.4.2
```

### Error: "No module named 'pytest'"
```bash
pip install pytest
```

### Tests fallan por dependencias de Django
Usar el test independiente:
```bash
python simple_gpu_test.py
```

## Contribución

Para agregar nuevos tests:
1. Seguir el patrón de naming `test_*.py`
2. Usar mocks para dependencias externas
3. Incluir tests tanto positivos como negativos
4. Documentar el propósito de cada test
5. Verificar que los tests pasen en diferentes entornos