"""URL patterns for the tasks app."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('tasks/create/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:pk>/toggle/', views.task_toggle, name='task_toggle'),
    path('tasks/<int:pk>/pin/', views.task_pin, name='task_pin'),
    path('tasks/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('tasks/bulk/', views.bulk_action, name='bulk_action'),

    path('calendar/', views.calendar_view, name='calendar'),
    path('analytics/', views.analytics_view, name='analytics'),
    path('activity/', views.activity_view, name='activity'),

    path('categories/', views.category_list, name='categories'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    path('profile/', views.profile, name='profile'),
    path('settings/', views.settings_view, name='settings'),
]
