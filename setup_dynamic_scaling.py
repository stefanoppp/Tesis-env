#!/usr/bin/env python3
"""
Script de configuración automática para el escalado dinámico de Celery.
Este script configura todo lo necesario para que el sistema funcione inmediatamente.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def print_header():
    """Mostrar header del script"""
    print("\n" + "="*70)
    print("🚀 CONFIGURACIÓN AUTOMÁTICA DE ESCALADO DINÁMICO")
    print("   Sistema inteligente de escalado de workers de Celery")
    print("="*70 + "\n")

def check_system():
    """Verificar sistema y dependencias"""
    print("📋 Verificando sistema...")
    
    # Verificar Python
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("❌ Error: Se requiere Python 3.8 o superior")
        return False
    print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # Verificar SO
    os_name = platform.system()
    print(f"✅ Sistema operativo: {os_name}")
    
    # Verificar Docker (opcional)
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Docker disponible: {result.stdout.strip()}")
        else:
            print("⚠️  Docker no disponible (opcional para desarrollo local)")
    except FileNotFoundError:
        print("⚠️  Docker no encontrado (opcional para desarrollo local)")
    
    return True

def create_env_file():
    """Crear archivo .env con configuración por defecto"""
    print("\n📝 Configurando variables de entorno...")
    
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if env_file.exists():
        print("⚠️  Archivo .env ya existe, creando backup...")
        backup_file = Path('.env.backup')
        env_file.rename(backup_file)
        print(f"✅ Backup creado: {backup_file}")
    
    # Configuración por defecto optimizada
    env_content = """
# === CONFIGURACIÓN DE ESCALADO DINÁMICO ===
# Generado automáticamente por setup_dynamic_scaling.py

# Escalado dinámico habilitado
DYNAMIC_SCALING_ENABLED=true

# Límites de seguridad (80% para prevenir saturación)
CPU_THRESHOLD=80
MEMORY_THRESHOLD=80

# Configuración de Celery (se ajusta automáticamente según hardware)
CELERY_WORKER_AUTOSCALER=6,1
CELERY_WORKER_CONCURRENCY=2

# Redis para desarrollo local
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Configuración de monitoreo
SYSTEM_CHECK_INTERVAL=30
SCALING_COOLDOWN_SECONDS=60
MAX_SCALING_CHANGES_PER_HOUR=10

# Escalado agresivo para GPU (se detecta automáticamente)
AGGRESSIVE_GPU_SCALING=true

# Configuración de logging
SCALING_LOG_LEVEL=INFO

# Entorno de desarrollo
DJANGO_ENV=development
DEBUG=1
""".strip()
    
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print(f"✅ Archivo .env creado con configuración optimizada")
    return True

def create_directories():
    """Crear directorios necesarios"""
    print("\n📁 Creando directorios necesarios...")
    
    directories = [
        'logs',
        'media',
        'staticfiles',
        'MLPlatformApp/management',
        'MLPlatformApp/management/commands'
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Directorio: {directory}")
    
    return True

def install_dependencies():
    """Instalar dependencias de Python"""
    print("\n📦 Verificando dependencias de Python...")
    
    required_packages = [
        'django>=4.0',
        'celery>=5.2',
        'redis>=4.0',
        'psutil>=5.8',
        'python-decouple',
        'djangorestframework',
        'django-cors-headers',
        'flower>=1.2'
    ]
    
    print("Dependencias requeridas:")
    for package in required_packages:
        print(f"  • {package}")
    
    install = input("\n¿Instalar dependencias automáticamente? (y/N): ").lower().strip()
    
    if install == 'y' or install == 'yes':
        print("\n📦 Instalando dependencias...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install'] + required_packages, check=True)
            print("✅ Dependencias instaladas correctamente")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error instalando dependencias: {e}")
            return False
    else:
        print("⚠️  Instala las dependencias manualmente antes de continuar")
        return True

def detect_hardware():
    """Detectar hardware y mostrar configuración recomendada"""
    print("\n🔍 Detectando hardware del sistema...")
    
    try:
        import psutil
        
        # CPU
        cpu_count = psutil.cpu_count(logical=False)
        cpu_logical = psutil.cpu_count(logical=True)
        print(f"✅ CPU: {cpu_count} cores físicos, {cpu_logical} lógicos")
        
        # RAM
        memory = psutil.virtual_memory()
        memory_gb = memory.total / (1024**3)
        print(f"✅ RAM: {memory_gb:.1f} GB")
        
        # GPU (intentar detectar)
        gpu_detected = False
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
            if result.returncode == 0:
                gpu_detected = True
                print("✅ GPU NVIDIA detectada")
        except:
            pass
        
        if not gpu_detected:
            print("ℹ️  GPU no detectada o no disponible")
        
        # Recomendaciones
        print("\n🎯 Configuración recomendada:")
        
        if gpu_detected:
            print("  • Estrategia: GPU optimizada")
            print("  • Workers: 1-6 (escalado agresivo)")
            print("  • Concurrencia: 1-2 por worker")
            print("  • n_jobs: 2-3 cores por tarea")
        elif memory_gb >= 8:
            print("  • Estrategia: CPU balanceada")
            print("  • Workers: 1-4 (escalado moderado)")
            print("  • Concurrencia: 2-4 por worker")
            print("  • n_jobs: 2-4 cores por tarea")
        else:
            print("  • Estrategia: CPU conservadora")
            print("  • Workers: 1-3 (escalado conservador)")
            print("  • Concurrencia: 1-2 por worker")
            print("  • n_jobs: 1-2 cores por tarea")
        
        print(f"  • Límites de seguridad: CPU<80%, RAM<80%")
        print(f"  • Monitoreo: cada 30 segundos")
        
        return True
        
    except ImportError:
        print("⚠️  psutil no disponible, instala dependencias primero")
        return False

def show_usage_instructions():
    """Mostrar instrucciones de uso"""
    print("\n" + "="*70)
    print("🎯 INSTRUCCIONES DE USO")
    print("="*70)
    
    print("\n🐳 OPCIÓN 1: Con Docker (Recomendado)")
    print("   docker-compose up -d")
    print("   docker-compose logs -f scaling-monitor")
    print("   # Flower: http://localhost:5555")
    
    print("\n💻 OPCIÓN 2: Desarrollo Local")
    print("   # Terminal 1: Redis")
    print("   docker run -d -p 6379:6379 redis:7-alpine")
    print("   ")
    print("   # Terminal 2: Django")
    print("   python manage.py runserver")
    print("   ")
    print("   # Terminal 3: Celery con autoscale")
    print("   celery -A backend worker --autoscale=6,1 --loglevel=info")
    print("   ")
    print("   # Terminal 4: Monitor de escalado")
    print("   python manage.py start_dynamic_scaling --verbose")
    
    print("\n📊 MONITOREO")
    print("   # Ver estado del sistema")
    print("   python manage.py start_dynamic_scaling --dry-run --verbose")
    print("   ")
    print("   # Ver configuración de hardware")
    print("   python manage.py hardware_config")
    print("   ")
    print("   # Logs del escalado")
    print("   tail -f logs/scaling.log")
    
    print("\n🔧 CONFIGURACIÓN")
    print("   # Editar límites de seguridad")
    print("   export CPU_THRESHOLD=70")
    print("   export MEMORY_THRESHOLD=75")
    print("   ")
    print("   # Cambiar intervalo de monitoreo")
    print("   export SYSTEM_CHECK_INTERVAL=15")
    
    print("\n📚 DOCUMENTACIÓN")
    print("   • README_ESCALADO_DINAMICO.md - Guía completa")
    print("   • DYNAMIC_SCALING_POLICY.md - Política detallada")
    print("   • .env.example - Variables de entorno")
    
    print("\n" + "="*70)
    print("✅ ¡CONFIGURACIÓN COMPLETADA!")
    print("   El sistema está listo para escalar automáticamente")
    print("   sin saturar tu PC. ¡Disfruta! 🚀")
    print("="*70 + "\n")

def main():
    """Función principal"""
    print_header()
    
    # Verificar que estamos en el directorio correcto
    if not Path('manage.py').exists():
        print("❌ Error: Ejecuta este script desde el directorio raíz del proyecto Django")
        print("   (donde está manage.py)")
        sys.exit(1)
    
    steps = [
        ("Verificar sistema", check_system),
        ("Crear archivo .env", create_env_file),
        ("Crear directorios", create_directories),
        ("Instalar dependencias", install_dependencies),
        ("Detectar hardware", detect_hardware),
    ]
    
    for step_name, step_func in steps:
        print(f"\n🔄 {step_name}...")
        if not step_func():
            print(f"❌ Error en: {step_name}")
            sys.exit(1)
    
    show_usage_instructions()

if __name__ == '__main__':
    main()