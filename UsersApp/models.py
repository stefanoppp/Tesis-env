from django.db import models

# generamos user por default de django---------
from django.contrib.auth.models import User
# ------------------
import uuid
from django.utils import timezone
# Creamos perfil para el user con los datos extra que no vienen por default

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Campos adicionales
    phone = models.CharField(max_length=20, blank=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, null=True, blank=True)
    token_created_at = models.DateTimeField(null=True, blank=True)

    def token_is_valid(self):
        if not self.token_created_at:
            return False
        elapsed = timezone.now() - self.token_created_at
        return elapsed.total_seconds() < 300  # 5 min

    def __str__(self):
        return f"Perfil de {self.user.username}"
