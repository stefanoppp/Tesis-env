from .base_imports import *
from celery import shared_task
@shared_task
def actualizar_estado_csv(csv_id):
    try:
        # Obtener el objeto CSV por su ID
        obj = CSVModel.objects.get(id=csv_id)
        
        # Actualizar el estado a True (procesado correctamente)
        obj.is_ready = True
        obj.save()

        logger.info(f"Estado de CSV ID: {csv_id} actualizado a 'is_ready=True'.")
    except Exception as e:
        logger.error(f"Error actualizando estado de CSV ID: {csv_id}: {str(e)}")

