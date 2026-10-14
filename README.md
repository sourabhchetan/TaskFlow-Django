# TaskFlow — Django Task Management

A responsive, full-stack task management application built with Django and Django REST Framework. TaskFlow helps users organize work, track deadlines, build recurring tasks, and review productivity from a personalized dashboard.

> **Live demo:** https://todo-list-django-r92l.onrender.com/  
> **Repository:** https://github.com/sourabhchetan/TaskFlow-Django

## Features

### Task management
- Create, edit, complete/reopen, pin, and delete tasks.
- Set Low, Medium, or High priority.
- Organize tasks with color-coded categories.
- Add due dates, due times, and attachments (PDF, image, Word, text, CSV, and Excel; 5 MB limit).
- Create daily, weekly, monthly, or custom-interval recurring tasks.
- Configure reminder offsets for tasks.

### Productivity views
- **Dashboard:** task statistics, completion progress, quick filters, search, sorting, and pagination.
- **Calendar:** monthly calendar with task counts and a daily agenda.
- **Analytics:** completion rate, priority/category breakdowns, and weekly productivity charts.
- **Categories:** create, rename, and delete categories.
- **Profile:** account statistics and email updates.
- **Settings:** theme, default priority, dashboard view, sort order, and reminder preference.

### Platform and security
- Django authentication: registration, login, logout, and password reset.
- Django REST Framework API.
- Light, dark, and system theme options.
- Responsive desktop, tablet, and mobile layouts.
- Django Admin.
- Custom 403, 404, and 500 error pages.
- User-scoped task and category access in both web views and API endpoints.
- Automated tests for authentication, task operations, recurrence, categories, analytics/calendar, and user isolation.

## Tech stack

- **Backend:** Python, Django, Django REST Framework
- **Database:** SQLite for local development; PostgreSQL supported for deployment
- **Frontend:** Django Templates, HTML, CSS, vanilla JavaScript
- **Production static files:** WhiteNoise
- **Production server:** Gunicorn
- **Hosting configuration:** Render Blueprint (`render.yaml`)

## Project structure

```text
TaskFlow-Django/
├── manage.py
├── requirements.txt
├── build.sh
├── Procfile
├── render.yaml
├── .env.example
├── config/                 # Django settings, URLs, WSGI/ASGI
├── tasks/                  # Main web app, models, templates, static files, tests
├── api/                    # Django REST Framework API
└── templates/              # Shared and authentication templates
```

## Run locally

### 1. Clone the repository

```bash
git clone https://github.com/sourabhchetan/TaskFlow-Django.git
cd TaskFlow-Django
```

### 2. Create and activate a virtual environment

**Windows PowerShell**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS/Linux**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables (optional for local development)

Copy `.env.example` to `.env` and update values if needed.

**Windows PowerShell**
```powershell
Copy-Item .env.example .env
```

**macOS/Linux**
```bash
cp .env.example .env
```

Do not commit `.env` or production secrets to Git.

### 5. Apply migrations and start the server

```bash
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/ and register an account. A new account is configured with a profile and starter categories.

### 6. Create an admin account (optional)

```bash
python manage.py createsuperuser
```

Then visit http://127.0.0.1:8000/admin/.

## Database configuration

The app uses SQLite by default for local development. To use PostgreSQL, set `DATABASE_URL` to a PostgreSQL connection URL. Render can provide this variable through the Blueprint configuration.

The first run against a new database requires migrations:

```bash
python manage.py migrate
```

A new PostgreSQL database starts empty; it does not automatically import records from a local `db.sqlite3` file.

## REST API

The API is served under `/api/`. Endpoints require authentication through session or token authentication.

| Method | Endpoint | Description |
|---|---|---|
| GET, POST | `/api/tasks/` | List or create your tasks |
| GET, PUT, PATCH, DELETE | `/api/tasks/<id>/` | Retrieve, update, or delete one of your tasks |
| POST | `/api/tasks/<id>/complete/` | Complete a task; recurring tasks may generate their next occurrence |
| POST | `/api/tasks/<id>/pin/` | Toggle a task's pinned state |
| GET, POST | `/api/categories/` | List or create your categories |
| GET, PUT, PATCH, DELETE | `/api/categories/<id>/` | Retrieve, update, or delete one of your categories |

Task listing supports filters such as `?completed=true`, `?priority=high`, and `?search=term`.

For token authentication, request a token from `/api/auth-token/` with your username and password, then include it in subsequent requests:

```http
Authorization: Token YOUR_TOKEN
```

The browsable API can be opened at `/api/tasks/` after signing in.

## Deploy to Render

This repository includes `render.yaml` for a Render Blueprint deployment.

1. Push the repository to GitHub.
2. In the Render dashboard, choose **New + → Blueprint**.
3. Select `sourabhchetan/TaskFlow-Django`, branch `main`, and Blueprint path `render.yaml`.
4. Review the proposed `todo-list-django` web service and `todo-list-db` PostgreSQL database, including their plans and any charges.
5. Click **Deploy Blueprint** and wait for the web service deployment to finish.
6. Open the service's public `onrender.com` URL and test registration, login, and task creation.

The Blueprint is configured to use the production build/start commands declared in the repository. Render should provide the database connection through `DATABASE_URL`; keep secrets in Render's environment settings rather than in GitHub.

### After deployment

- Confirm the service status is **Live**.
- Test the homepage, static CSS/JavaScript, registration, login, and task CRUD.
- Check the Render logs if the build or startup fails.
- Create a Django superuser from the Render service Shell if admin access is required:

```bash
python manage.py createsuperuser
```

### Deployment limitations

- **Uploaded attachments:** Render's default service filesystem is ephemeral. Task attachment files stored locally may be lost when the service restarts or redeploys. Use a persistent disk or external object storage if attachments must persist.
- **Database migration:** PostgreSQL starts as a separate empty database; local SQLite records are not copied automatically.
- **Costs:** Review the current service and database plans in Render before deploying or changing the Blueprint.

## Environment variables

The project reads configuration from environment variables. Common settings include:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret key; set a strong private value in production |
| `DJANGO_DEBUG` | Enables/disables debug mode; use `False` in production |
| `DJANGO_ALLOWED_HOSTS` | Hosts allowed to serve the app |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins, including the `https://` scheme |
| `DJANGO_TIME_ZONE` | Time zone used by Django |
| `DJANGO_SECURE_COOKIES` | Enables secure cookies in production |
| `DATABASE_URL` | PostgreSQL connection URL; supplied by Render Blueprint when configured |
| `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Optional explicit database configuration when `DATABASE_URL` is unset |

Check `.env.example` and `config/settings.py` for the exact supported defaults and behavior.

## Run tests and checks

```bash
python manage.py test
python manage.py check
python manage.py makemigrations --check
```

## Security notes

- Tasks and categories are scoped to the authenticated user in web views and API queries.
- API object permissions check ownership.
- Forms and serializers validate submitted data on the server.
- Django handles password hashing and authentication.
- File uploads are checked for extension and size.
- Never commit `.env`, production secret keys, or database credentials.

## Future improvements

- Deliver real email/push reminders with a background job system.
- Add drag-and-drop task ordering.
- Support shared or collaborative task lists.
- Build a separate client using the REST API.
