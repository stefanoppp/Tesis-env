from django.urls import path
from .views import (
    RegisterView, 
    VerifyTokenView, 
    LoginView,
    SessionExtendView,
    ActivityHeartbeatView,
    SessionStatusView,
    CustomTokenRefreshView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify/', VerifyTokenView.as_view(), name='verify'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('session/extend/', SessionExtendView.as_view(), name='session_extend'),
    path('session/heartbeat/', ActivityHeartbeatView.as_view(), name='activity_heartbeat'),
    path('session/status/', SessionStatusView.as_view(), name='session_status'),
]
