from django.urls import path
from .views import (
    CreateModelView, 
    MyModelsListView, 
    ModelStatusView,
    ModelMetricsView,
    PredictView,
    MarketplaceView
)

urlpatterns = [
    path('create/', CreateModelView.as_view(), name='create_model'),
    path('mymodels/', MyModelsListView.as_view(), name='my_models_list'),
    path('status/<int:model_id>/', ModelStatusView.as_view(), name='model_status'),
    path('metrics/<int:model_id>/', ModelMetricsView.as_view(), name='model_metrics'),
    path('predict/<int:model_id>/', PredictView.as_view(), name='predict'),
    path('marketplace/', MarketplaceView.as_view(), name='marketplace'),
]