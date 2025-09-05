from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('api/upload/', views.upload_dataset, name='upload_dataset'),
    path('api/datasets/', views.list_datasets, name='list_datasets'),
    path('api/analysis/<int:dataset_id>/', views.get_dataset_analysis, name='dataset_analysis'),
]