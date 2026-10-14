"""
Django settings for the To-Do List project.

Designed to run out-of-the-box on SQLite for local development while being
ready to switch to PostgreSQL (or any other database) in production by only
changing environment variables — no code changes required.
"""
import os
from pathlib import Path

try:
    # Optional: loads a local .env file if python-dotenv is installed and the
    # file exists. Never required — every setting below also has a sane
    # os.environ.get(...) fallback, so the project still runs without it.
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    # Optional for the same reason as python-dotenv above: only needed when
    # DATABASE_URL is actually set (i.e. on Render / any host that provides a
    # Postgres connection string). Local SQLite development never imports it.
    import dj_database_url
except ImportError:
    dj_database_url = None

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
# The secret key is read from the environment so it is never hard-coded or
# committed to source control. A development fallback is provided only so the
# project runs immediately after cloning; ALWAYS set DJANGO_SECRET_KEY in any
# real deployment.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-dev-only-key-change-me-before-deploying'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if h.strip()
]

# Render sets this automatically to the service's live *.onrender.com
# hostname. Appending it here means the app accepts Render's assigned
# hostname out of the box, without the person having to look it up and add
# it to DJANGO_ALLOWED_HOSTS by hand after the first deploy.
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Needed for CSRF-protected POSTs (login, task forms, etc.) to work over
# HTTPS once the app is live — Django 4+ requires the scheme. Empty by
# default so local HTTP development is unaffected; set explicitly in
# production (see .env.example / README). No wildcard trust by default.
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if o.strip()
]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    'rest_framework',
    'rest_framework.authtoken',

    'tasks.apps.TasksConfig',
    'api.apps.ApiConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Must come immediately after SecurityMiddleware and before everything
    # else — this is what lets gunicorn serve CSS/JS/icons itself in
    # production without a separate static-file host (nginx/S3/CDN), which
    # is what makes `collectstatic` + WhiteNoise sufficient for Render.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'tasks.context_processors.sidebar_counts',
                'tasks.context_processors.notification_bell',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Three ways to configure the database, in priority order — none of them
# require a code change to switch:
#   1. DATABASE_URL set (Render, or any host that provides a Postgres
#      connection string) -> parsed by dj-database-url. SSL is required
#      automatically whenever DEBUG=False, since Render's managed Postgres
#      expects/enforces an SSL connection.
#   2. DB_ENGINE=postgresql set manually (e.g. a local Postgres via
#      docker-compose) -> the original explicit-variable block, unchanged.
#   3. Neither set -> SQLite, the zero-config local-dev default. Never
#      overwritten or migrated-from automatically by either branch above.
_database_url = os.environ.get('DATABASE_URL')
if _database_url and dj_database_url is not None:
    DATABASES = {
        'default': dj_database_url.config(
            default=_database_url,
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
elif os.environ.get('DB_ENGINE') == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'todo_list'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('DJANGO_TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise's compressed+hashed storage only in production (DEBUG=False).
# It requires collectstatic to have already run and written a manifest
# (staticfiles.json) before any {% static %} URL can resolve at all — in
# production that's guaranteed by build.sh running collectstatic before
# gunicorn ever starts, but `runserver`/`manage.py test` locally never run
# collectstatic first, so the exact same backend there raised
# "the file '...' could not be found" on every single page load the moment
# this was (wrongly) left unconditional. Local dev/test instead gets
# Django's own plain, un-hashed static storage — the same thing this project
# used before WhiteNoise was added, and it needs no manifest to work.
#
# Non-strict manifest mode in production is the beginner-safe choice on top
# of that: a strict manifest makes collectstatic/runtime raise if any
# referenced static file is ever missing, which is a confusing first-deploy
# failure mode; non-strict just serves that one file unhashed instead of
# hard-failing the whole app.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}
WHITENOISE_MANIFEST_STRICT = False

# Task attachments are stored here. In production, point MEDIA_ROOT at
# persistent storage (or swap in django-storages for S3/GCS) — local disk
# storage is fine for development only.
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
# Session auth covers the browsable API for logged-in browser use (CSRF
# protected, like the rest of the site); Token auth covers external/API
# clients such as scripts, curl, or a future mobile app. Every endpoint
# requires authentication by default, and object-level ownership is
# re-checked per-request by api.permissions.IsOwner.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ---------------------------------------------------------------------------
# Auth redirects
# ---------------------------------------------------------------------------
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# ---------------------------------------------------------------------------
# Security hardening (relaxed automatically while DEBUG=True)
# ---------------------------------------------------------------------------
CSRF_COOKIE_HTTPONLY = False  # kept False so the toast/JS layer can read errors if needed
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'

if not DEBUG:
    SESSION_COOKIE_SECURE = os.environ.get('DJANGO_SECURE_COOKIES', 'True') == 'True'
    CSRF_COOKIE_SECURE = os.environ.get('DJANGO_SECURE_COOKIES', 'True') == 'True'
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Render (like Heroku) terminates HTTPS at its own proxy and forwards
    # plain HTTP internally, setting this header to say the original request
    # was HTTPS. Without telling Django to trust it, request.is_secure()
    # would read as False behind the proxy — the one line that matters here
    # is secure cookies above actually getting sent, and `python manage.py
    # runserver` locally is unaffected since this whole block only runs when
    # DEBUG=False.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Pagination default used by views
TASKS_PER_PAGE = 9
