from django.urls import path
from .views import RegisterView, VerifyTokenView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify/', VerifyTokenView.as_view(), name='verify'),
]
