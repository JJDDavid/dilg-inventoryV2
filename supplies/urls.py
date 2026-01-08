from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_settings, name='profile_settings'),
    path('list/', views.supply_list, name='supply_list'),
    path('add/', views.supply_create, name='supply_create'),
    path('<int:pk>/edit/', views.supply_update, name='supply_update'),
    path('<int:pk>/delete/', views.supply_delete, name='supply_delete'),
    path('incoming/', views.record_incoming, name='record_incoming'),
    path('incoming/<int:pk>/receive/', views.receive_incoming, name='incoming_receive'),
]
