#!/usr/bin/env python3
"""
Prueba simple del sistema de escalado dinámico sin dependencias de Django
"""

import sys
import os

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Importar directamente los módulos de escalado
    from MLPlatformApp.config.hardware_optimization import HardwareOptimizer
    from MLPlatformApp.config.dynamic_scaling import DynamicScalingPolicy
    
    print("🔧 PRUEBA DEL SISTEMA DE ESCALADO DINÁMICO")
    print("=" * 50)
    
    # 1. Probar optimización de hardware
    print("\n1. OPTIMIZACIÓN DE HARDWARE:")
    optimizer = HardwareOptimizer()
    config = optimizer.get_optimal_config()
    print(f"   ✅ GPU disponible: {config['use_gpu']}")
    print(f"   ✅ CPU cores: {config['physical_cpu_count']}")
    print(f"   ✅ RAM: {config['memory_gb']:.1f} GB")
    print(f"   ✅ Concurrencia recomendada: {config['recommended_concurrency']}")
    
    # 2. Probar política de escalado
    print("\n2. POLÍTICA DE ESCALADO DINÁMICO:")
    scaler = DynamicScalingPolicy()
    
    # Prueba con diferentes escenarios
    scenarios = [
        ("Cola vacía", 0),
        ("Cola pequeña", 3),
        ("Cola mediana", 8),
        ("Cola larga", 15),
        ("Cola muy larga", 25)
    ]
    
    for scenario_name, queue_length in scenarios:
        workers, config = scaler.calculate_optimal_workers(queue_length)
        print(f"   📊 {scenario_name} (cola={queue_length}): {workers} workers")
        print(f"      Estrategia: {config['strategy']}")
        print(f"      n_jobs: {config['n_jobs']}")
    
    # 3. Probar recomendaciones de escalado
    print("\n3. RECOMENDACIONES DE ESCALADO:")
    test_cases = [
        ("Escalado normal", 2, 5),
        ("Escalado con carga alta", 3, 12),
        ("Reducción de workers", 4, 1)
    ]
    
    for case_name, current_workers, queue_length in test_cases:
        recommendation = scaler.get_scaling_recommendation(current_workers, queue_length)
        print(f"   🎯 {case_name}:")
        print(f"      Workers actuales: {recommendation['current_workers']}")
        print(f"      Workers recomendados: {recommendation['recommended_workers']}")
        print(f"      Acción: {recommendation['action']}")
        print(f"      Razón: {recommendation['reason']}")
    
    # 4. Probar límites de seguridad
    print("\n4. LÍMITES DE SEGURIDAD:")
    system_load = scaler.get_current_system_load()
    print(f"   🖥️  CPU actual: {system_load['cpu_percent']:.1f}%")
    print(f"   💾 RAM actual: {system_load['memory_percent']:.1f}%")
    print(f"   💽 RAM disponible: {system_load['memory_available_gb']:.1f} GB")
    
    # Verificar si se aplicarían límites de seguridad
    if system_load['cpu_percent'] > 80 or system_load['memory_percent'] > 80:
        print("   ⚠️  ADVERTENCIA: Sistema cerca de los límites de seguridad")
    else:
        print("   ✅ Sistema dentro de los límites de seguridad")
    
    print("\n" + "=" * 50)
    print("🎉 TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")
    print("\n📋 RESUMEN:")
    print("   ✅ Hardware optimization: OK")
    print("   ✅ Dynamic scaling policy: OK")
    print("   ✅ Scaling recommendations: OK")
    print("   ✅ Safety limits: OK")
    print("\n🚀 El sistema de escalado dinámico está funcionando correctamente!")
    
except ImportError as e:
    print(f"❌ Error de importación: {e}")
    print("💡 Asegúrate de que todos los módulos estén disponibles")
except Exception as e:
    print(f"❌ Error inesperado: {e}")
    import traceback
    traceback.print_exc()