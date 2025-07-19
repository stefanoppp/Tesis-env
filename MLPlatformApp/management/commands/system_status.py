from django.core.management.base import BaseCommand
from django.conf import settings
from MLPlatformApp.models import AIModel, UserPlan
import psutil
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Muestra el estado actual del sistema y la cola de entrenamiento'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Mostrar información detallada incluyendo modelos individuales'
        )
    
    def handle(self, *args, **options):
        detailed = options['detailed']
        
        # Obtener configuración
        ml_settings = getattr(settings, 'ML_PLATFORM_SETTINGS', {})
        max_global_queue = ml_settings.get('MAX_GLOBAL_QUEUE_SIZE', 20)
        max_user_pending = ml_settings.get('MAX_USER_PENDING_MODELS', 3)
        
        self.stdout.write(
            self.style.SUCCESS('=== ESTADO DEL SISTEMA ML PLATFORM ===')
        )
        
        # 1. Recursos del sistema
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            self.stdout.write('\n📊 RECURSOS DEL SISTEMA:')
            self.stdout.write(f'  CPU: {cpu_percent}%')
            self.stdout.write(f'  Memoria: {memory.percent}% ({memory.used // (1024**3)}GB / {memory.total // (1024**3)}GB)')
            self.stdout.write(f'  Disco: {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)')
            
            # Alertas de recursos
            if cpu_percent > ml_settings.get('MAX_CPU_PERCENT', 85):
                self.stdout.write(self.style.ERROR('  ⚠️  CPU SOBRECARGADO'))
            if memory.percent > ml_settings.get('MAX_MEMORY_PERCENT', 85):
                self.stdout.write(self.style.ERROR('  ⚠️  MEMORIA SOBRECARGADA'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error obteniendo recursos: {str(e)}'))
        
        # 2. Estado de la cola
        pending_models = AIModel.objects.filter(status='pending')
        training_models = AIModel.objects.filter(status='training')
        completed_models = AIModel.objects.filter(status='completed')
        failed_models = AIModel.objects.filter(status='failed')
        
        self.stdout.write('\n🚀 ESTADO DE LA COLA:')
        self.stdout.write(f'  Pendientes: {pending_models.count()}/{max_global_queue} ({round((pending_models.count()/max_global_queue)*100, 1)}%)')
        self.stdout.write(f'  Entrenando: {training_models.count()}')
        self.stdout.write(f'  Completados: {completed_models.count()}')
        self.stdout.write(f'  Fallidos: {failed_models.count()}')
        
        # Alertas de cola
        if pending_models.count() >= max_global_queue * 0.8:
            self.stdout.write(self.style.WARNING('  ⚠️  COLA CASI LLENA'))
        if pending_models.count() >= max_global_queue:
            self.stdout.write(self.style.ERROR('  🚫 COLA LLENA - RECHAZANDO NUEVOS MODELOS'))
        
        # 3. Estadísticas de usuarios
        total_users = UserPlan.objects.count()
        active_users_today = AIModel.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=1)
        ).values('user').distinct().count()
        
        self.stdout.write('\n👥 USUARIOS:')
        self.stdout.write(f'  Total registrados: {total_users}')
        self.stdout.write(f'  Activos hoy: {active_users_today}')
        
        # 4. Planes de usuario
        plan_stats = {}
        for plan_type in ['free', 'basic', 'premium', 'enterprise']:
            count = UserPlan.objects.filter(plan_type=plan_type).count()
            plan_stats[plan_type] = count
        
        self.stdout.write('\n💳 DISTRIBUCIÓN DE PLANES:')
        for plan, count in plan_stats.items():
            self.stdout.write(f'  {plan.capitalize()}: {count} usuarios')
        
        # 5. Información detallada (opcional)
        if detailed:
            self.stdout.write('\n📋 MODELOS EN COLA (DETALLADO):')
            
            if pending_models.exists():
                self.stdout.write('  Pendientes:')
                for model in pending_models.order_by('queue_position')[:10]:
                    user_plan = UserPlan.get_user_plan(model.user)
                    self.stdout.write(
                        f'    #{model.queue_position} - {model.name} '
                        f'(Usuario: {model.user.username}, Plan: {user_plan.plan_type})'
                    )
                if pending_models.count() > 10:
                    self.stdout.write(f'    ... y {pending_models.count() - 10} más')
            
            if training_models.exists():
                self.stdout.write('  Entrenando:')
                for model in training_models:
                    elapsed = timezone.now() - model.started_at if model.started_at else None
                    elapsed_str = f'{elapsed.total_seconds()/60:.1f}min' if elapsed else 'N/A'
                    self.stdout.write(
                        f'    {model.name} (Tiempo: {elapsed_str})'
                    )
        
        # 6. Recomendaciones
        self.stdout.write('\n💡 RECOMENDACIONES:')
        
        if failed_models.count() > 10:
            self.stdout.write('  🧹 Ejecutar: python manage.py cleanup_failed_models')
        
        if pending_models.count() > max_global_queue * 0.7:
            self.stdout.write('  ⚡ Considerar aumentar workers de Celery')
        
        if cpu_percent > 80 or memory.percent > 80:
            self.stdout.write('  🔧 Verificar recursos del servidor')
        
        self.stdout.write('\n✅ Reporte completado')