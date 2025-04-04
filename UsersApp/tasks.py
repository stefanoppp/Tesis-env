from celery import shared_task

@shared_task
def enviar_mensaje_debug():
    print("Tarea Celery ejecutada correctamente.")
    return "Hola desde Celery"
