from django.urls import path
from .views import CreateModelView, ModelStatusView, MyModelsView,PredictView, DeleteModelView

urlpatterns = [
    path('create/', CreateModelView.as_view(), name='create_model'),
    path('my_models/', MyModelsView.as_view(), name='my_models'),
    path('status/<uuid:model_id>/', ModelStatusView.as_view(), name='model_status'),
    path('models/predict/<uuid:model_id>/', PredictView.as_view(), name='predict'),
    path('models/delete/<uuid:model_id>/', DeleteModelView.as_view(), name='delete_model'),  
]
