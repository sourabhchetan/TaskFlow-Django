#!/usr/bin/env bash
# Render's build command. Runs on every deploy, before the start command.
#
# set -o errexit: stop and fail the build visibly on the first error,
# instead of silently continuing (e.g. deploying with migrations that never
# actually ran because an earlier step failed).
set -o errexit

pip install -r requirements.txt

# Collects tasks/static/* plus admin/DRF's built-in static files into
# STATIC_ROOT (staticfiles/), hashed and compressed by WhiteNoise, so
# gunicorn can serve CSS/JS/icons itself with no separate static host.
python manage.py collectstatic --no-input

# Applies any pending migrations against whatever DATABASES resolves to in
# this environment (Postgres on Render via DATABASE_URL, SQLite locally).
# Never resets or drops anything — only ever applies forward migrations.
python manage.py migrate
