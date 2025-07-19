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
        self.gpu_available = self._detect_gpu()
        
    def _detect_gpu(self) -> bool:
        """Detecta si hay GPU NVIDIA disponible con CUDA"""
        try:
            import cuml
            logger.info("GPU NVIDIA con cuML detectada")
            return True
        except ImportError:
            try:
                import torch
                if torch.cuda.is_available():
                    logger.info("GPU NVIDIA con PyTorch detectada")
                    return True
            except ImportError:
                pass
            
            try:
                import tensorflow as tf
                if tf.config.list_physical_devices('GPU'):
                    logger.info("GPU detectada con TensorFlow")
                    return True
            except ImportError:
                pass
                
        logger.info("No se detectó GPU NVIDIA compatible")
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
            'cpu_count_logical': self.cpu_count,
            'cpu_count_physical': self.physical_cpu_count,
            'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            'memory_total_gb': round(self.memory_gb, 2),
            'memory_available_gb': round(memory.available / (1024**3), 2),
            'memory_percent_used': memory.percent,
            'gpu_available': self.gpu_available,
            'platform': os.name,
        }
    
    def log_system_info(self):
        """Registra información del sistema en los logs"""
        info = self.get_system_info()
        config = self.get_optimal_config()
        
        logger.info("=== INFORMACIÓN DEL SISTEMA ===")
        logger.info(f"CPU Cores (Lógicos): {info['cpu_count_logical']}")
        logger.info(f"CPU Cores (Físicos): {info['cpu_count_physical']}")
        logger.info(f"RAM Total: {info['memory_total_gb']} GB")
        logger.info(f"RAM Disponible: {info['memory_available_gb']} GB")
        logger.info(f"GPU Disponible: {info['gpu_available']}")
        
        logger.info("=== CONFIGURACIÓN OPTIMIZADA ===")
        logger.info(f"Usar GPU: {config['use_gpu']}")
        logger.info(f"n_jobs recomendado: {config['n_jobs']}")
        logger.info(f"Concurrencia Celery recomendada: {config['recommended_concurrency']}")
        logger.info(f"Modelos preferidos: {config['preferred_models']}")
        logger.info(f"CV Folds: {config['cv_folds']}")
        logger.info(f"Tiempo por modelo: {config['budget_time']} minutos")

# Instancia global para usar en toda la aplicación
hardware_optimizer = HardwareOptimizer()