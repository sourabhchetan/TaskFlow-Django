"""URL configuration for the To-Do List project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

from tasks import views as task_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Django's built-in auth views provide login, logout, and password
    # reset/change flows. Templates for these live in templates/registration/.
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/register/', task_views.register, name='register'),

    # REST API (see api/urls.py). /api-auth/ adds a login/logout link to the
    # browsable API; /api/auth-token/ issues a token for script/API clients.
    path('api/', include('api.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('api/auth-token/', obtain_auth_token, name='api-token-auth'),

    path('', include('tasks.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'tasks.views.error_404'
handler403 = 'tasks.views.error_403'
handler500 = 'tasks.views.error_500'
