from django.urls import path
from .views import UploadCSVView, LaunchProcessingView, GetResultsView, CSVStatusView

urlpatterns = [
    path('upload/', UploadCSVView.as_view(), name='upload_csv'),
    path('process/', LaunchProcessingView.as_view(), name='launch_processing'),
    path('results/', GetResultsView.as_view(), name='get_results'),
    path('status/<int:csv_id>/', CSVStatusView.as_view(), name='csv-status'),
]