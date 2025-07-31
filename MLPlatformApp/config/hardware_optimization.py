import os
import psutil
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class HardwareOptimizer:
    """
    Clase para optimizar automáticamente la configuración según el hardware disponible
    """
    
    def __init__(self):
        self.cpu_count = psutil.cpu_count(logical=True)
        self.physical_cpu_count = psutil.cpu_count(logical=False)
        self.memory_gb = psutil.virtual_memory().total / (1024**3)
        self.cpu_info = self._detect_cpu_info()
        self.gpu_available = self._detect_gpu()
        
    def _detect_cpu_info(self) -> Dict[str, Any]:
        """Detecta información detallada del procesador"""
        cpu_info = {
            'logical_cores': self.cpu_count,
            'physical_cores': self.physical_cpu_count,
            'brand': 'Unknown',
            'architecture': 'Unknown',
            'frequency': None
        }
        
        try:
            # Obtener frecuencia del CPU
            freq = psutil.cpu_freq()
            if freq:
                cpu_info['frequency'] = {
                    'current': round(freq.current, 2),
                    'min': round(freq.min, 2) if freq.min else None,
                    'max': round(freq.max, 2) if freq.max else None
                }
        except Exception as e:
            logger.warning(f"Error al obtener frecuencia del CPU: {e}")
            
        try:
            # Detectar información del CPU en Windows
            import platform
            import subprocess
            
            if platform.system() == "Windows":
                # Obtener información del procesador con WMIC
                result = subprocess.run(['wmic', 'cpu', 'get', 'name'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        cpu_info['brand'] = lines[1].strip()
                        
                # Obtener arquitectura
                result = subprocess.run(['wmic', 'cpu', 'get', 'architecture'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        arch_code = lines[1].strip()
                        arch_map = {'0': 'x86', '1': 'MIPS', '2': 'Alpha', '3': 'PowerPC', 
                                   '5': 'ARM', '6': 'ia64', '9': 'x64'}
                        cpu_info['architecture'] = arch_map.get(arch_code, f"Unknown ({arch_code})")
            else:
                # Para sistemas Unix/Linux
                cpu_info['brand'] = platform.processor()
                cpu_info['architecture'] = platform.machine()
                
        except Exception as e:
            logger.warning(f"Error al detectar información del CPU: {e}")
            
        try:
            # Información adicional con cpuinfo (si está disponible)
            import cpuinfo
            info = cpuinfo.get_cpu_info()
            if info:
                cpu_info['brand'] = info.get('brand_raw', cpu_info['brand'])
                cpu_info['architecture'] = info.get('arch', cpu_info['architecture'])
                cpu_info['vendor'] = info.get('vendor_id_raw', 'Unknown')
                cpu_info['flags'] = info.get('flags', [])
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Error al obtener información detallada del CPU: {e}")
            
        logger.info(f"🖥️ CPU detectado: {cpu_info['brand']} ({cpu_info['physical_cores']} cores físicos, {cpu_info['logical_cores']} lógicos)")
        return cpu_info
        
    def _detect_gpu(self) -> bool:
        """Detecta si hay GPU disponible con múltiples métodos (NVIDIA y AMD)"""
        # Verificar si la detección de GPU está deshabilitada
        if os.getenv('DISABLE_GPU_DETECTION', '0') == '1':
            logger.info("🚫 Detección de GPU deshabilitada por variable de entorno DISABLE_GPU_DETECTION")
            return False
            
        gpu_info = []
        
        # Método 1: cuML (RAPIDS) - Solo NVIDIA
        try:
            import cuml
            gpu_info.append("cuML (RAPIDS)")
            logger.info("✅ GPU NVIDIA con cuML/RAPIDS detectada")
            return True
        except ImportError:
            pass
            
        # Método 2: PyTorch CUDA (NVIDIA)
        try:
            import torch
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                device_name = torch.cuda.get_device_name(0) if device_count > 0 else "Unknown"
                gpu_info.append(f"PyTorch CUDA - {device_count} GPU(s) - {device_name}")
                logger.info(f"✅ GPU NVIDIA detectada con PyTorch: {device_name} ({device_count} dispositivos)")
                return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Error al detectar GPU NVIDIA con PyTorch: {e}")
            
        # Método 3: PyTorch ROCm (AMD)
        try:
            import torch
            # Verificar si ROCm está disponible
            if hasattr(torch.backends, 'hip') and torch.backends.hip.is_available():
                device_count = torch.hip.device_count() if hasattr(torch, 'hip') else 0
                if device_count > 0:
                    device_name = torch.hip.get_device_name(0) if hasattr(torch.hip, 'get_device_name') else "AMD GPU"
                    gpu_info.append(f"PyTorch ROCm - {device_count} GPU(s) - {device_name}")
                    logger.info(f"✅ GPU AMD detectada con PyTorch ROCm: {device_name} ({device_count} dispositivos)")
                    return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Error al detectar GPU AMD con PyTorch ROCm: {e}")
            
        # Método 4: TensorFlow (NVIDIA y AMD)
        try:
            import tensorflow as tf
            gpus = tf.config.list_physical_devices('GPU')
            if gpus:
                gpu_info.append(f"TensorFlow - {len(gpus)} GPU(s)")
                logger.info(f"✅ GPU detectada con TensorFlow: {len(gpus)} dispositivos")
                return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Error al detectar GPU con TensorFlow: {e}")
            
        # Método 5: nvidia-ml-py (NVIDIA Management Library)
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
                    gpu_info.append(f"NVML - {name}")
                logger.info(f"✅ GPU NVIDIA detectada con NVML: {device_count} dispositivos")
                return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Error al detectar GPU NVIDIA con NVML: {e}")
            
        # Método 6: Detección básica con subprocess (Windows - NVIDIA y AMD)
        try:
            import subprocess
            import platform
            if platform.system() == "Windows":
                result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'name'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    output = result.stdout.upper()
                    if 'NVIDIA' in output:
                        gpu_info.append("Windows WMIC - NVIDIA detectada")
                        logger.info("✅ GPU NVIDIA detectada via Windows WMIC")
                        return True
                    elif 'AMD' in output or 'RADEON' in output:
                        gpu_info.append("Windows WMIC - AMD detectada")
                        logger.info("✅ GPU AMD detectada via Windows WMIC")
                        return True
        except Exception as e:
            logger.warning(f"Error al detectar GPU con WMIC: {e}")
            
        # Método 7: rocm-smi para AMD (Linux)
        try:
            import subprocess
            import platform
            if platform.system() == "Linux":
                result = subprocess.run(['rocm-smi'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and 'GPU' in result.stdout:
                    gpu_info.append("ROCm SMI - AMD detectada")
                    logger.info("✅ GPU AMD detectada via rocm-smi")
                    return True
        except Exception as e:
            logger.warning(f"Error al detectar GPU AMD con rocm-smi: {e}")
                
        logger.info("❌ No se detectó GPU compatible (NVIDIA o AMD)")
        return False
    
    def get_optimal_config(self) -> Dict[str, Any]:
        """Retorna configuración óptima según hardware disponible"""
        config = {
            'use_gpu': self.gpu_available,
            'cpu_count': self.cpu_count,
            'physical_cpu_count': self.physical_cpu_count,
            'memory_gb': self.memory_gb,
        }
        
        # Configurar n_jobs según disponibilidad de GPU y CPU
        if self.gpu_available:
            # Con GPU, usar menos CPU cores para evitar conflictos
            config['n_jobs'] = min(2, self.physical_cpu_count)
            config['recommended_concurrency'] = 1  # Para Celery
        else:
            # Sin GPU, optimizar uso de CPU pero sin saturar
            if self.memory_gb >= 16:
                # Sistema con suficiente RAM
                config['n_jobs'] = min(4, max(2, self.physical_cpu_count // 2))
                config['recommended_concurrency'] = min(3, max(1, self.physical_cpu_count // 4))
            elif self.memory_gb >= 8:
                # Sistema con RAM moderada
                config['n_jobs'] = min(2, max(1, self.physical_cpu_count // 3))
                config['recommended_concurrency'] = min(2, max(1, self.physical_cpu_count // 6))
            else:
                # Sistema con poca RAM
                config['n_jobs'] = 1
                config['recommended_concurrency'] = 1
        
        # Configuración de modelos según recursos
        # Los 10 mejores modelos para clasificación y regresión según benchmarks académicos
        
        if self.gpu_available:
            # Con GPU: Los 10 mejores modelos con aceleración GPU
            config['preferred_models_classification'] = [
                'lr',        # Logistic Regression
                'rf',        # Random Forest
                'xgboost',   # XGBoost
                'lightgbm',  # LightGBM
                'catboost',  # CatBoost
                'et',        # Extra Trees
                'gbc',       # Gradient Boosting
                'ada',       # AdaBoost
                'svm',       # Support Vector Machine
                'ridge'      # Ridge Classifier
            ]
            config['preferred_models_regression'] = [
                'rf',        # Random Forest
                'xgboost',   # XGBoost
                'lightgbm',  # LightGBM
                'catboost',  # CatBoost
                'et',        # Extra Trees
                'gbr',       # Gradient Boosting
                'ada',       # AdaBoost
                'ridge',     # Ridge Regression
                'lasso',     # Lasso Regression
                'en'         # Elastic Net
            ]
            config['cv_folds'] = 5
            config['budget_time'] = 2.0  # 2 minutos máximo por modelo en comparación
        elif self.memory_gb >= 8 and self.physical_cpu_count >= 4:
            # Sistema medio: Los 10 mejores modelos optimizados para CPU
            config['preferred_models_classification'] = [
                'lr',        # Logistic Regression
                'rf',        # Random Forest
                'xgboost',   # XGBoost
                'lightgbm',  # LightGBM
                'dt',        # Decision Tree
                'nb',        # Naive Bayes
                'et',        # Extra Trees
                'gbc',       # Gradient Boosting
                'ada',       # AdaBoost
                'ridge'      # Ridge Classifier
            ]
            config['preferred_models_regression'] = [
                'rf',        # Random Forest
                'xgboost',   # XGBoost
                'lightgbm',  # LightGBM
                'dt',        # Decision Tree
                'et',        # Extra Trees
                'gbr',       # Gradient Boosting
                'ada',       # AdaBoost
                'ridge',     # Ridge Regression
                'lasso',     # Lasso Regression
                'en'         # Elastic Net
            ]
            config['cv_folds'] = 3
            config['budget_time'] = 1.0  # 1 minuto máximo por modelo en comparación
        else:
            # Sistema básico: Los 6 modelos más eficientes
            config['preferred_models_classification'] = [
                'lr',        # Logistic Regression
                'dt',        # Decision Tree
                'nb',        # Naive Bayes
                'ridge',     # Ridge Classifier
                'rf',        # Random Forest (reducido)
                'ada'        # AdaBoost
            ]
            config['preferred_models_regression'] = [
                'lr',        # Linear Regression
                'dt',        # Decision Tree
                'ridge',     # Ridge Regression
                'lasso',     # Lasso Regression
                'rf',        # Random Forest (reducido)
                'ada'        # AdaBoost
            ]
            config['cv_folds'] = 3
            config['budget_time'] = 0.5  # 30 segundos máximo por modelo en comparación
            
        # Para compatibilidad con código existente, usar clasificación por defecto
        config['preferred_models'] = config['preferred_models_classification']
            
        return config
    
    def get_system_info(self) -> Dict[str, Any]:
        """Retorna información detallada del sistema"""
        memory = psutil.virtual_memory()
        
        return {
            'cpu_info': self.cpu_info,
            'cpu_count_logical': self.cpu_count,
            'cpu_count_physical': self.physical_cpu_count,
            'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            'memory_total_gb': round(self.memory_gb, 2),
            'memory_available_gb': round(memory.available / (1024**3), 2),
            'memory_percent_used': memory.percent,
            'gpu_available': self.gpu_available,
            'platform': os.name,
            'platform_detailed': {
                'system': os.name,
                'release': os.uname().release if hasattr(os, 'uname') else 'Unknown',
                'version': os.uname().version if hasattr(os, 'uname') else 'Unknown'
            }
        }
    
    def log_system_info(self):
        """Registra información del sistema en los logs"""
        info = self.get_system_info()
        config = self.get_optimal_config()
        
        logger.info("=== 🖥️ INFORMACIÓN DEL SISTEMA ===")
        logger.info(f"🔧 Procesador: {info['cpu_info']['brand']}")
        logger.info(f"⚙️ Arquitectura: {info['cpu_info']['architecture']}")
        logger.info(f"🧮 CPU Cores (Físicos): {info['cpu_count_physical']}")
        logger.info(f"🧮 CPU Cores (Lógicos): {info['cpu_count_logical']}")
        
        if info['cpu_info']['frequency']:
            freq = info['cpu_info']['frequency']
            logger.info(f"⚡ Frecuencia CPU: {freq['current']} MHz (Max: {freq['max']} MHz)")
            
        logger.info(f"💾 RAM Total: {info['memory_total_gb']} GB")
        logger.info(f"💾 RAM Disponible: {info['memory_available_gb']} GB ({100-info['memory_percent_used']:.1f}% libre)")
        logger.info(f"🎮 GPU Disponible: {'✅ Sí' if info['gpu_available'] else '❌ No'}")
        logger.info(f"🖥️ Sistema: {info['platform_detailed']['system']}")
        
        logger.info("=== ⚙️ CONFIGURACIÓN OPTIMIZADA ===")
        logger.info(f"🎮 Usar GPU: {'✅ Sí' if config['use_gpu'] else '❌ No'}")
        logger.info(f"⚡ n_jobs recomendado: {config['n_jobs']}")
        logger.info(f"🔄 Concurrencia Celery recomendada: {config['recommended_concurrency']}")
        logger.info(f"🤖 Modelos preferidos ({len(config['preferred_models'])}): {', '.join(config['preferred_models'][:5])}{'...' if len(config['preferred_models']) > 5 else ''}")
        logger.info(f"📊 CV Folds: {config['cv_folds']}")
        logger.info(f"⏱️ Tiempo por modelo: {config['budget_time']} minutos")
        
        # Mostrar recomendaciones adicionales
        if config['use_gpu']:
            logger.info("💡 Recomendación: Sistema con GPU detectada - Configuración optimizada para aceleración por GPU")
        else:
            logger.info("💡 Recomendación: Sistema sin GPU - Configuración optimizada para procesamiento por CPU")
            
        if info['memory_total_gb'] < 8:
            logger.warning("⚠️ Advertencia: RAM limitada detectada - Se usará configuración conservadora")
        elif info['memory_total_gb'] >= 16:
            logger.info("✅ Excelente: RAM abundante detectada - Se puede usar configuración agresiva")

# Instancia global para usar en toda la aplicación
hardware_optimizer = HardwareOptimizer()