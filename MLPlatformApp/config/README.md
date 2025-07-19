# Configuración Automática de Hardware

Este módulo proporciona optimización automática de hardware para la plataforma ML, detectando automáticamente las capacidades del sistema y configurando PyCaret y Celery de manera óptima.

## 🚀 Características

### Detección Automática de Hardware
- **CPU**: Detecta número de cores y uso actual
- **RAM**: Detecta memoria disponible y uso actual
- **GPU**: Detecta disponibilidad de RAPIDS cuML para aceleración GPU

### Optimización Automática
- **PyCaret**: Configura `n_jobs`, `use_gpu`, modelos preferidos, y tiempo de presupuesto
- **Celery**: Ajusta concurrencia automáticamente según recursos disponibles
- **Validación Cruzada**: Optimiza número de pliegues según recursos

## 📋 Uso

### 1. Verificar Configuración Actual

```bash
# Mostrar configuración recomendada
python manage.py hardware_config

# Mostrar información detallada
python manage.py hardware_config --verbose

# Mostrar comandos para aplicar configuración
python manage.py hardware_config --apply
```

### 2. Aplicar Configuración de Celery

La configuración se aplica automáticamente en `settings.py`, pero puedes reiniciar Celery con:

```bash
# Usar configuración automática (recomendado)
celery -A backend worker --loglevel=info -Q training

# O especificar concurrencia manualmente
celery -A backend worker --loglevel=info --concurrency=2 -Q training
```

### 3. Optimizaciones Adicionales

#### Para GPU (si está disponible)
```bash
# Instalar dependencias GPU
pip install cuml cudf-cu11 cupy-cuda11x

# Verificar instalación
python -c "import cuml; print('GPU acceleration available')"
```

#### Para CPU (optimizaciones Intel)
```bash
# Instalar optimizaciones CPU
pip install scikit-learn-intelex numba

# Las optimizaciones se activan automáticamente
```

## ⚙️ Configuración

### Parámetros Automáticos

El sistema configura automáticamente:

| Parámetro | GPU Disponible | CPU Medio | CPU Básico |
|-----------|----------------|-----------|------------|
| `n_jobs` | 1-2 | 2-4 | 1 |
| `use_gpu` | `True` | `False` | `False` |
| `cv_folds` | 5 | 3 | 3 |
| `budget_time` | 2.0 min | 1.0 min | 0.5 min |
| `celery_concurrency` | 1-2 | 2-3 | 1-2 |
| `modelos_clasificación` | 10 | 10 | 6 |
| `modelos_regresión` | 10 | 10 | 6 |

### Modelos Seleccionados

#### **Clasificación - Los 10 Mejores:**
**Con GPU (10 modelos):**
- Regresión Logística (lr)
- Random Forest (rf)
- XGBoost (xgboost)
- LightGBM (lightgbm)
- CatBoost (catboost)
- Extra Trees (et)
- Gradient Boosting (gbc)
- AdaBoost (ada)
- Support Vector Machine (svm)
- Ridge Classifier (ridge)

**CPU Medio (10 modelos):**
- Todos los anteriores excepto SVM, más:
- Árbol de Decisión (dt)
- Naive Bayes (nb)

**CPU Básico (6 modelos):**
- Regresión Logística (lr)
- Árbol de Decisión (dt)
- Naive Bayes (nb)
- Ridge Classifier (ridge)
- Random Forest (rf)
- AdaBoost (ada)

#### **Regresión - Los 10 Mejores:**
**Con GPU/CPU Medio (10 modelos):**
- Random Forest (rf)
- XGBoost (xgboost)
- LightGBM (lightgbm)
- CatBoost (catboost)
- Extra Trees (et)
- Gradient Boosting (gbr)
- AdaBoost (ada)
- Ridge Regression (ridge)
- Lasso Regression (lasso)
- Elastic Net (en)

**CPU Básico (6 modelos):**
- Regresión Linear (lr)
- Árbol de Decisión (dt)
- Ridge Regression (ridge)
- Lasso Regression (lasso)
- Random Forest (rf)
- AdaBoost (ada)

## 🔧 Personalización

### Modificar Umbrales

En `hardware_optimization.py`:

```python
# Cambiar umbrales de recursos
CPU_USAGE_THRESHOLD = 70  # % CPU máximo
RAM_USAGE_THRESHOLD = 70  # % RAM máximo
MIN_AVAILABLE_RAM_GB = 2  # RAM mínima requerida
```

### Configuración Manual

Puedes sobrescribir la configuración automática:

```python
# En settings.py
CELERY_WORKER_CONCURRENCY = 1  # Forzar concurrencia específica

# En training.py
setup(
    data=data,
    target=target_column,
    n_jobs=1,  # Forzar número de jobs
    use_gpu=False,  # Deshabilitar GPU
    # ... otros parámetros
)
```

## 📊 Monitoreo

### Logs del Sistema

El sistema registra automáticamente:

```
INFO - Hardware detected: 8 cores, 16.0 GB RAM, GPU: Yes
INFO - Optimal config: n_jobs=2, use_gpu=True, concurrency=2
INFO - GPU enabled with 2 CPU jobs
INFO - Using models: ['lr', 'rf', 'xgboost', 'lightgbm', 'catboost']
```

### Comando de Estado del Sistema

```bash
# Ver estado actual del sistema
python manage.py system_status
```

## ⏱️ Explicación de Tiempos

### Diferencia entre `budget_time` y `training_time`

- **`budget_time`**: Tiempo MÁXIMO que PyCaret puede usar por modelo durante la **comparación** (compare_models)
  - Es un límite, no el tiempo real
  - Si un modelo tarda menos, termina antes
  - Si tarda más, se detiene automáticamente
  - Se mide en **minutos**

- **`training_time`**: Tiempo REAL que tardó todo el proceso de entrenamiento
  - Incluye carga de datos, preprocesamiento, comparación y guardado
  - Se mide en **segundos**
  - Es el tiempo total desde inicio hasta fin

### Ejemplo:
```
budget_time = 1.0 min  # Máximo 1 minuto por modelo en comparación
training_time = 45.2 sec  # Tiempo real total del entrenamiento
```

## 🚨 Solución de Problemas

### CPU al 100%

1. **Reducir concurrencia de Celery:**
   ```bash
   celery -A backend worker --concurrency=1 -Q training
   ```

2. **Limitar jobs de PyCaret:**
   - El sistema automáticamente detecta alta carga y reduce `n_jobs`
   - Puedes forzar `n_jobs=1` en casos extremos

3. **Reducir tiempo límite:**
   ```python
   compare_models(include=['lr', 'rf'], budget_time=0.25)  # 15 segundos máximo
   ```

4. **Usar menos modelos:**
   ```python
   compare_models(include=['lr', 'dt', 'nb'], n_select=1)  # Solo 3 modelos rápidos
   ```

### Problemas de GPU

1. **Verificar instalación:**
   ```bash
   python -c "import cuml; print('OK')"
   ```

2. **Fallback a CPU:**
   - El sistema automáticamente usa CPU si GPU falla
   - Revisa logs para mensajes de error

3. **Conflictos de memoria GPU:**
   - Reduce concurrencia de Celery a 1
   - Usa menos pliegues de validación cruzada

### Memoria Insuficiente

1. **El sistema automáticamente:**
   - Reduce número de pliegues CV
   - Limita modelos simultáneos
   - Ajusta tiempo de presupuesto

2. **Configuración manual:**
   ```python
   setup(data=data, target=target, fold=3)  # Menos pliegues
   compare_models(budget_time=0.25)  # Menos tiempo por modelo
   ```

## 📈 Mejores Prácticas

1. **Monitoreo Continuo:**
   - Ejecuta `python manage.py hardware_config` regularmente
   - Revisa logs de entrenamiento para detectar problemas

2. **Configuración Gradual:**
   - Comienza con configuración conservadora
   - Aumenta recursos gradualmente según rendimiento

3. **Pruebas de Carga:**
   - Prueba con datasets pequeños primero
   - Monitorea uso de recursos durante entrenamiento

4. **Backup de Configuración:**
   - Documenta configuraciones que funcionan bien
   - Mantén configuración manual como respaldo

## 🔄 Actualizaciones

Para actualizar la configuración después de cambios de hardware:

```bash
# Reiniciar Django para recargar configuración
python manage.py runserver

# Reiniciar Celery con nueva configuración
celery -A backend worker --loglevel=info -Q training

# Verificar nueva configuración
python manage.py hardware_config --verbose
```