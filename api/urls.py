"""API URL routing, registered under /api/ in config/urls.py."""
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, TaskViewSet

router = DefaultRouter()
router.register('tasks', TaskViewSet, basename='api-task')
router.register('categories', CategoryViewSet, basename='api-category')

urlpatterns = router.urls
