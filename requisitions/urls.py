from django.urls import path

from . import views

urlpatterns = [
    path('select/', views.select_supplies, name='request_select_supplies'),
    path('new/', views.request_create, name='request_create'),
    path('list/', views.request_list, name='request_list'),
    path('history/', views.request_history, name='request_history'),
    path('history/my/', views.request_history_user, name='request_history_user'),
    path('detail/<int:pk>/', views.request_detail, name='request_detail'),
    path('receipt/<int:pk>/', views.request_receipt, name='request_receipt'),
    path('<int:pk>/approve/', views.approve_request, name='approve_request'),
    path('<int:pk>/reject/', views.reject_request, name='reject_request'),
    path('<int:pk>/archive/', views.archive_request, name='archive_request'),
]
