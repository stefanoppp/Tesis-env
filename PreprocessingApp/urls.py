from django.urls import path
from .views import UploadCSVView, LaunchProcessingView, MyCSVListView, CSVStatusView,CSVMetricasView

urlpatterns = [
    path('upload/', UploadCSVView.as_view(), name='upload_csv'),
    path('process/', LaunchProcessingView.as_view(), name='launch_processing'),
    path('csvlist/', MyCSVListView.as_view(), name='my_csv_list'),
    path('status/<int:csv_id>/', CSVStatusView.as_view(), name='csv-status'),
    path('metricas/<int:csv_id>/', CSVMetricasView.as_view(), name='csv-metricas'),
]