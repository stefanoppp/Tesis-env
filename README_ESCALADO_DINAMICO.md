# 🚀 Escalado Dinámico de Workers de Celery

## 📋 Resumen

Este sistema implementa una política completa de escalado dinámico para workers de Celery que:

- ✅ **Previene saturación** manteniendo CPU y RAM bajo 80%
- ✅ **Escala automáticamente** según la carga del sistema y cola de tareas
- ✅ **Triggers Inmediatos** respuesta instantánea a condiciones críticas
- ✅ **Detección de Picos** identifica aumentos súbitos de carga
- ✅ **Doble Monitoreo** regular (30s) + inmediato (5s mínimo)
- ✅ **Se adapta al hardware** (GPU vs CPU, RAM disponible)
- ✅ **Monitorea en tiempo real** cada 30 segundos
- ✅ **Funciona localmente y en la nube**

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Django App    │    │  Scaling Monitor │    │  Celery Workers │
│                 │    │                  │    │                 │
│ • Middleware    │◄──►│ • System Load    │◄──►│ • Auto-scale    │
│ • Settings      │    │ • Queue Length   │    │ • 1-6 workers   │
│ • Commands      │    │ • Recommendations│    │ • GPU/CPU aware │
└─────────────────┘    └──────────────────┘    └─────────────────┘
           │                       │                       │
           └───────────────────────┼───────────────────────┘
                                   ▼
                          ┌─────────────────┐
                          │      Redis      │
                          │                 │
                          │ • Task Queue    │
                          │ • Results       │
                          │ • Monitoring    │
                          └─────────────────┘
```

## ⚡ Sistema de Triggers Inmediatos

El sistema implementa **3 tipos de triggers** para respuesta rápida:

### 🚨 Trigger Crítico
- **Activación**: CPU > 85% O RAM > 85%
- **Respuesta**: Inmediata (<5 segundos)
- **Acción**: Escalado agresivo (workers -1 adicional)

### 📈 Trigger de Picos
- **Activación**: Aumento súbito >20% en CPU/RAM
- **Detección**: Comparación con promedio de últimas 3 mediciones
- **Respuesta**: Inmediata

### 🔄 Monitoreo Regular
- **Activación**: Cada 30 segundos
- **Umbrales**: CPU > 80% O RAM > 80%
- **Respuesta**: Escalado estándar

### 🛡️ Protecciones
- **Cooldown**: Mínimo 5 segundos entre triggers inmediatos
- **Historial**: Mantiene últimas 5 mediciones para detectar picos
- **Límites**: Nunca reduce a menos de 1 worker

## 🛠️ Componentes Implementados

### 1. **Política de Escalado** (`dynamic_scaling.py`)
- Detecta hardware automáticamente (GPU/CPU/RAM)
- Calcula workers óptimos según carga
- Aplica límites de seguridad del 80%

### 2. **Configuración Dinámica** (`celery_config.py`)
- Ajusta concurrencia según hardware
- Modifica timeouts según carga
- Optimiza prefetch y max_tasks

### 3. **Middleware de Monitoreo** (`middleware.py`)
- Verifica carga cada 30 segundos
- Aplica escalado automáticamente
- Registra métricas y recomendaciones

### 4. **Comando de Monitoreo** (`start_dynamic_scaling.py`)
- Monitoreo continuo independiente
- Modo dry-run para testing
- Configuración flexible

### 5. **Configuración Docker** (`docker-compose.yml`)
- Límites de recursos por contenedor
- Autoscale de Celery habilitado
- Monitor dedicado de escalado

## 🚀 Uso Rápido

### Opción 1: Con Docker (Recomendado)

```bash
# 1. Configurar variables de entorno
cp .env.example .env
# Editar .env según tus necesidades

# 2. Levantar todo el sistema
docker-compose up -d

# 3. Ver logs del escalado
docker-compose logs -f scaling-monitor

# 4. Monitorear en Flower
# http://localhost:5555
```

### Opción 2: Desarrollo Local

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar variables de entorno
export DYNAMIC_SCALING_ENABLED=true
export CPU_THRESHOLD=80
export MEMORY_THRESHOLD=80

# 3. Iniciar Redis
docker run -d -p 6379:6379 redis:7-alpine

# 4. Iniciar Django
python manage.py runserver

# 5. Iniciar Celery con autoscale
celery -A backend worker --autoscale=6,1 --loglevel=info

# 6. Iniciar monitor (en otra terminal)
python manage.py start_dynamic_scaling --verbose
```

## ⚙️ Configuración Detallada

### Variables de Entorno Principales

```bash
# Escalado dinámico básico
DYNAMIC_SCALING_ENABLED=true    # Habilitar/deshabilitar
CPU_THRESHOLD=80                # Límite de CPU (%)
MEMORY_THRESHOLD=80             # Límite de RAM (%)

# Triggers inmediatos
CRITICAL_CPU_THRESHOLD=85       # Trigger crítico CPU (%)
CRITICAL_MEMORY_THRESHOLD=85    # Trigger crítico RAM (%)
SPIKE_THRESHOLD=20              # Detección de picos (%)
IMMEDIATE_CHECK_INTERVAL=5      # Intervalo triggers inmediatos (s)

# Celery autoscale
CELERY_WORKER_AUTOSCALER=6,1    # max_workers,min_workers
CELERY_WORKER_CONCURRENCY=2     # Workers por proceso

# Monitoreo
SYSTEM_CHECK_INTERVAL=30        # Intervalo de verificación (s)
SCALING_COOLDOWN_SECONDS=60     # Tiempo entre escalados (s)
```

### Configuración por Hardware

#### Con GPU Detectada:
```
• Workers: 1-6 (escalado agresivo)
• Concurrencia: 1-2 por worker
• n_jobs: 2-3 cores por tarea
• Estrategia: Priorizar GPU, CPU secundario
```

#### Solo CPU (RAM >= 8GB):
```
• Workers: 1-4 (escalado moderado)
• Concurrencia: 2-4 por worker
• n_jobs: 2-4 cores por tarea
• Estrategia: Balanceado CPU/RAM
```

#### Solo CPU (RAM < 8GB):
```
• Workers: 1-3 (escalado conservador)
• Concurrencia: 1-2 por worker
• n_jobs: 1-2 cores por tarea
• Estrategia: Conservar memoria
```

## 📊 Monitoreo y Logs

### Ver Estado del Sistema

```bash
# Logs del escalado dinámico
tail -f logs/scaling.log

# Estado de Celery
celery -A backend inspect active
celery -A backend inspect stats

# Métricas del sistema
python manage.py start_dynamic_scaling --dry-run --verbose
```

### Flower Dashboard

Accede a `http://localhost:5555` para ver:
- Workers activos
- Tareas en cola
- Métricas de rendimiento
- Historial de tareas

## 🔧 Comandos Útiles

### Monitoreo Manual

```bash
# Monitoreo básico con triggers inmediatos
python manage.py start_dynamic_scaling

# Configuración personalizada completa
python manage.py start_dynamic_scaling \
  --interval=60 \
  --immediate-check-interval=3 \
  --cpu-threshold=70 \
  --memory-threshold=75 \
  --critical-cpu-threshold=85 \
  --critical-memory-threshold=85 \
  --spike-threshold=25 \
  --verbose

# Solo mostrar recomendaciones (no aplicar)
python manage.py start_dynamic_scaling --dry-run --verbose

# Triggers inmediatos más sensibles
python manage.py start_dynamic_scaling \
  --critical-cpu-threshold=80 \
  --critical-memory-threshold=80 \
  --spike-threshold=15 \
  --immediate-check-interval=3
```

### Escalado Manual

```bash
# Escalar workers manualmente
docker-compose up --scale celery-training=3

# Reiniciar workers
docker-compose restart celery-training

# Ver configuración actual
python manage.py hardware_config
```

## 📈 Ejemplos de Escalado

### Escenario 1: Sistema con GPU

```
🖥️  Hardware: GPU + 8 cores + 16GB RAM
📊 Carga inicial: CPU 20%, RAM 30%, Cola 0
🎯 Configuración: 1 worker, 2 concurrencia

📈 Aumenta carga: CPU 60%, RAM 45%, Cola 5
🎯 Escalado: 3 workers, 2 concurrencia

📈 Pico de carga: CPU 75%, RAM 70%, Cola 12
🎯 Escalado: 6 workers, 1 concurrencia

📉 Sobrecarga: CPU 85%, RAM 82%
🎯 Reducción: 4 workers, 1 concurrencia
```

### Escenario 2: Sistema Solo CPU

```
🖥️  Hardware: 4 cores + 8GB RAM
📊 Carga inicial: CPU 25%, RAM 35%, Cola 0
🎯 Configuración: 1 worker, 2 concurrencia

📈 Aumenta carga: CPU 55%, RAM 50%, Cola 3
🎯 Escalado: 2 workers, 2 concurrencia

📈 Alta carga: CPU 70%, RAM 65%, Cola 8
🎯 Escalado: 3 workers, 2 concurrencia

📉 Sobrecarga: CPU 82%, RAM 78%
🎯 Reducción: 2 workers, 1 concurrencia
```

## 🚨 Solución de Problemas

### Problema: Workers no escalan

```bash
# Verificar configuración
echo $DYNAMIC_SCALING_ENABLED
echo $CELERY_WORKER_AUTOSCALER

# Verificar logs
docker-compose logs celery-training
docker-compose logs scaling-monitor

# Reiniciar servicios
docker-compose restart celery-training scaling-monitor
```

### Problema: Sistema sobrecargado

```bash
# Reducir límites temporalmente
export CPU_THRESHOLD=60
export MEMORY_THRESHOLD=60

# Forzar escalado conservador
export CELERY_WORKER_AUTOSCALER=2,1

# Reiniciar con nueva configuración
docker-compose restart celery-training
```

### Problema: Escalado muy agresivo

```bash
# Aumentar cooldown
export SCALING_COOLDOWN_SECONDS=120

# Limitar cambios por hora
export MAX_SCALING_CHANGES_PER_HOUR=5

# Deshabilitar escalado agresivo
export AGGRESSIVE_GPU_SCALING=false
```

## 🌐 Despliegue en Producción

### AWS/Azure/GCP

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  celery-training:
    environment:
      - DYNAMIC_SCALING_ENABLED=true
      - CPU_THRESHOLD=85
      - MEMORY_THRESHOLD=85
      - CELERY_WORKER_AUTOSCALER=12,2
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '1.0'
          memory: 2G
      replicas: 2
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-workers
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: celery
        env:
        - name: DYNAMIC_SCALING_ENABLED
          value: "true"
        - name: CPU_THRESHOLD
          value: "80"
        - name: MEMORY_THRESHOLD
          value: "80"
        resources:
          limits:
            cpu: "2"
            memory: "4Gi"
          requests:
            cpu: "500m"
            memory: "1Gi"
```

## 📚 Referencias

- [Documentación de Celery Autoscale](https://docs.celeryproject.org/en/stable/userguide/workers.html#autoscaling)
- [Política de Escalado Completa](./DYNAMIC_SCALING_POLICY.md)
- [Configuración de Hardware](./MLPlatformApp/config/README.md)
- [Monitoreo con Flower](https://flower.readthedocs.io/)

---

**🎯 ¡El sistema está listo para manejar el escalado automáticamente sin saturar tu PC!**

Para cualquier duda o problema, revisa los logs en `logs/scaling.log` o ejecuta el monitoreo en modo verbose.