from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json


class Command(BaseCommand):
    help = 'Configura las tareas programadas de Celery Beat en la base de datos'

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('🔄 Configurando tareas programadas de Celery Beat...'))
        
        # Crear intervalos de tiempo
        daily_schedule, created = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.DAYS,
        )
        
        every_30_min_schedule, created = IntervalSchedule.objects.get_or_create(
            every=30,
            period=IntervalSchedule.MINUTES,
        )
        
        # Crear tarea de limpieza de modelos fallidos
        cleanup_task, created = PeriodicTask.objects.get_or_create(
            name='Limpieza automática de modelos fallidos',
            defaults={
                'task': 'UsersApp.tasks.cleanup_failed_models',
                'interval': daily_schedule,
                'enabled': True,
                'description': 'Elimina automáticamente modelos con estado "failed" más antiguos que el umbral configurado'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✅ Tarea de limpieza creada: cada 24 horas'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Tarea de limpieza ya existe'))
        
        # Crear tarea de detección de modelos colgados
        stuck_task, created = PeriodicTask.objects.get_or_create(
            name='Detección de modelos colgados',
            defaults={
                'task': 'UsersApp.tasks.detect_stuck_models',
                'interval': every_30_min_schedule,
                'enabled': True,
                'description': 'Detecta y marca como fallidos los modelos que llevan mucho tiempo en entrenamiento'
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✅ Tarea de detección creada: cada 30 minutos'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Tarea de detección ya existe'))
        
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('📋 RESUMEN DE TAREAS PROGRAMADAS:'))
        self.stdout.write(f'  • {cleanup_task.name}: {"ACTIVA" if cleanup_task.enabled else "INACTIVA"}')
        self.stdout.write(f'  • {stuck_task.name}: {"ACTIVA" if stuck_task.enabled else "INACTIVA"}')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('🎉 Configuración de Celery Beat completada!'))
        self.stdout.write(self.style.HTTP_INFO('💡 Para iniciar Celery Beat: celery -A backend beat --loglevel=info'))