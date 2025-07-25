from django.urls import path
from .views import CreateModelView, ModelStatusView, MyModelsView,PredictView, DeleteModelView,PublicModelsView,ModelInfoView, DeleteMultipleModelsView, SuggestTaskTypeView

urlpatterns = [
    path('create/', CreateModelView.as_view(), name='create_model'),
    path('my_models/', MyModelsView.as_view(), name='my_models'),
    path('public/', PublicModelsView.as_view(), name='public_models'),
    path('status/<uuid:model_id>/', ModelStatusView.as_view(), name='model_status'),
    path('predict/<uuid:model_id>/', PredictView.as_view(), name='predict'),
    path('delete/<uuid:model_id>/', DeleteModelView.as_view(), name='delete_model'),  
    path('delete-multiple/', DeleteMultipleModelsView.as_view(), name='delete_multiple_models'),
    path('info/<uuid:model_id>/', ModelInfoView.as_view(), name='model_info'),
    path('suggest-task-type/', SuggestTaskTypeView.as_view(), name='suggest_task_type'),
]
