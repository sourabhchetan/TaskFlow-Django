# To-Do List

A full-stack task management application built with Django, Django REST Framework, SQLite/PostgreSQL, and a responsive modern frontend.

## Features

**Core task management**
- Create, edit, complete/reopen, pin, and delete tasks — all scoped to the signed-in user
- Priorities (Low/Medium/High), user-managed Categories with colors, due date + time
- Task attachments (PDF/image/Word/text/CSV/Excel, 5MB limit, extension + size validated)
- Recurring tasks (Daily/Weekly/Monthly/Custom-interval) with automatic next-occurrence generation on completion, duplicate-safe and end-date aware
- Optional reminder offsets (10 min / 30 min / 1 hour / 1 day before due)

**Views**
- **Dashboard** — personalized greeting, live stats, completion progress bar, Today's Overview, Priority Summary, quick filters (All/Today/Upcoming/Overdue/High/Pinned/Completed), search, sort, pagination
- **Calendar** — monthly grid with task-count indicators, prev/next/today navigation, and a per-day agenda list (agenda-first on mobile)
- **Analytics** — completion rate, tasks by priority, tasks by category, weekly productivity chart (all rendered as lightweight CSS bar charts, no charting library)
- **Categories** — create, rename, delete; deleting a category leaves its tasks "Uncategorized" rather than deleting them
- **Profile** — account stats and completion rate, with the ability to update your email
- **Settings** — real, persisted preferences: theme (Light/Dark/System), default priority, default dashboard view, default sort, reminder toggle

**Platform**
- Django Authentication — register, login, logout, password reset
- **REST API** (Django REST Framework) — see [API Documentation](#api-documentation)
- Light/Dark mode (per-device override via localStorage, plus a persisted account-level preference)
- Fully responsive — dedicated layouts for desktop (sidebar), tablet, and mobile (hamburger menu + bottom nav, agenda-first calendar)
- A small hand-drawn inline-SVG icon system (no third-party icon library, no emoji-as-UI)
- Toast notifications, custom empty states, custom 404/403/500 error pages
- Django Admin configured with useful list filters, search, and ordering
- Automated tests covering auth, CRUD, recurrence, categories, analytics/calendar, and — repeatedly — cross-user isolation (both web views and the API)

## Tech Stack

- **Backend:** Python, Django, Django ORM, Django Forms, Django Authentication, Django Admin, Django REST Framework
- **Database:** SQLite for local development (PostgreSQL-ready — see [Database](#database))
- **Frontend:** Django Templates, HTML5, CSS3 (custom design system with CSS variables for theming), vanilla JavaScript

## Screenshots

_Add screenshots of the dashboard, calendar, analytics, and mobile view here._

## Project Architecture

```text
todo-list/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── config/                 # Project configuration
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── tasks/                  # Main web application
│   ├── migrations/
│   ├── templates/tasks/
│   ├── static/tasks/{css,js}/
│   ├── templatetags/       # {% icon %}, query_transform, etc.
│   ├── admin.py
│   ├── apps.py
│   ├── context_processors.py
│   ├── forms.py
│   ├── models.py           # Task, Category, Profile
│   ├── services.py         # stats, recurrence math, calendar grid — kept out of views.py
│   ├── signals.py          # auto-create Profile + default Categories per user
│   ├── urls.py
│   ├── views.py
│   └── tests/               # test_auth, test_tasks, test_recurrence, test_categories,
│                            # test_isolation, test_calendar_analytics
│
├── api/                    # REST API application
│   ├── serializers.py
│   ├── permissions.py      # IsOwner — object-level ownership check
│   ├── views.py            # TaskViewSet, CategoryViewSet
│   ├── urls.py
│   └── tests.py
│
└── templates/
    ├── base.html
    ├── 404.html / 403.html / 500.html
    └── registration/       # login, register, password reset
```

## Database Design

```text
User (Django's built-in auth user)
 │
 ├── Profile (1:1)          — theme, default priority/view/sort, reminders_enabled
 │
 ├── Category (1:N)         — id, user, name, color, created_at
 │                             unique per (user, name)
 │
 └── Task (1:N)
       ├── category  → Category (N:1, nullable — SET_NULL on delete)
       ├── parent_task → Task (self FK, nullable) — links a recurring chain
       │                  to its original task
       └── fields: title, description, priority, due_date, due_time,
                   completed, completed_at, pinned, created_at, updated_at,
                   is_recurring, recurrence_type, recurrence_interval,
                   recurrence_end_date, reminder_offset, attachment
```

Every `Task` and `Category` query is scoped with `user=request.user` (web views) or an equivalent `get_queryset()` filter plus an `IsOwner` object-permission check (API), so one user can never read, modify, or delete another user's data — including by guessing an id in a URL. See `tasks/tests/test_isolation.py` and `api/tests.py` for the tests that verify this directly.

## API Documentation

The API lives under `/api/` and is built with Django REST Framework. All endpoints require authentication.

### Authentication

Two methods are supported simultaneously:

- **Session authentication** — for the browsable API and any same-origin JS. Log in at `/api-auth/login/`, then requests from the browser (with the CSRF cookie) are authenticated automatically.
- **Token authentication** — for scripts, `curl`, or an external client. Obtain a token:

  ```bash
  curl -X POST http://127.0.0.1:8000/api/auth-token/ \
       -d "username=youruser&password=yourpassword"
  # -> {"token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4"}
  ```

  Then send it on every request:

  ```bash
  curl http://127.0.0.1:8000/api/tasks/ \
       -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4"
  ```

A user can only ever see and modify their **own** tasks and categories — enforced both by the queryset (`TaskViewSet.get_queryset`) and by the `IsOwner` permission class on every object-level action.

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/tasks/` | List your tasks. Supports `?completed=true`, `?priority=high`, `?search=...` |
| POST | `/api/tasks/` | Create a task |
| GET | `/api/tasks/<id>/` | Retrieve one task (yours only — 404 otherwise) |
| PUT / PATCH | `/api/tasks/<id>/` | Update a task |
| DELETE | `/api/tasks/<id>/` | Delete a task |
| POST | `/api/tasks/<id>/complete/` | Mark complete; generates the next occurrence if recurring |
| POST | `/api/tasks/<id>/pin/` | Toggle pinned |
| GET | `/api/categories/` | List your categories |
| POST | `/api/categories/` | Create a category |
| GET/PUT/PATCH/DELETE | `/api/categories/<id>/` | Retrieve/update/delete one category (yours only) |

#### Example: `GET /api/tasks/`

```text
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4

Response 200:
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Learn Django",
      "description": "",
      "category": 2,
      "category_name": "Study",
      "priority": "high",
      "priority_label": "High",
      "due_date": "2026-09-10",
      "due_time": "18:00:00",
      "completed": false,
      "pinned": false,
      "created_at": "2026-09-05T10:00:00Z",
      "updated_at": "2026-09-05T10:00:00Z",
      "completed_at": null,
      "is_recurring": false,
      "recurrence_type": "none",
      "recurrence_interval": 1,
      "recurrence_end_date": null,
      "reminder_offset": "none",
      "is_overdue": false,
      "countdown_text": "Due in 4d 8h"
    }
  ]
}
```

#### Example: `POST /api/tasks/` with a bad category (error response)

```text
Authorization: Token ...
Body: {"title": "Sneaky", "category": 99}

Response 400:
{"category": ["You can only assign your own categories."]}
```

#### Example: unauthenticated request

```text
GET /api/tasks/  (no Authorization header, no session cookie)

Response 401 or 403:
{"detail": "Authentication credentials were not provided."}
```

The full browsable API (with forms, auth, and live documentation of every field) is available by visiting any endpoint in a browser, e.g. `http://127.0.0.1:8000/api/tasks/`.

## Installation

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) copy environment config
cp .env.example .env            # Windows: copy .env.example .env

# 4. Apply database migrations
python manage.py migrate

# 5. Create an admin account
python manage.py createsuperuser

# 6. Run the development server
python manage.py runserver
```

Then open **http://127.0.0.1:8000/** and register a new account to get started. Every new account automatically gets a `Profile` and a starter set of categories (Personal, Work, Study, Project, Shopping, Other).

## Admin

The Django Admin is available at **http://127.0.0.1:8000/admin/** using the superuser credentials created above. From there you can inspect/search/filter all users, tasks, and categories.

## Database

The project ships configured for **SQLite** so it runs immediately with zero setup. To use **PostgreSQL** instead, there are two ways — neither requires a code change:

**Option A — `DATABASE_URL`** (what Render provides automatically, and the simplest option anywhere else too):

```bash
export DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME
```

**Option B — explicit variables** (e.g. a local Postgres via docker-compose), used only when `DATABASE_URL` is unset:

```bash
export DB_ENGINE=postgresql
export DB_NAME=todo_list
export DB_USER=postgres
export DB_PASSWORD=yourpassword
export DB_HOST=localhost
export DB_PORT=5432
```

`psycopg2-binary` is already in `requirements.txt` (a self-contained binary wheel — it installs fine even if you never touch Postgres locally).

Either way, run `python manage.py migrate` afterwards. This never reads from or copies your local `db.sqlite3` — a fresh Postgres database starts empty, same as any new Django database.

## Environment Variables

See `.env.example` for the full list. The most relevant:

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Secret key (always set a real value in production) | dev-only fallback |
| `DJANGO_DEBUG` | Enables/disables debug mode | `True` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated, scheme required (`https://...`) — needed once the site is served over HTTPS from a real domain | empty |
| `DJANGO_TIME_ZONE` | Timezone used for due dates/times | `UTC` |
| `DJANGO_SECURE_COOKIES` | Force secure cookies when `DEBUG=False` | `True` |
| `DATABASE_URL` | Full Postgres connection string (what Render provides) | unset → SQLite |
| `DB_ENGINE` | Set to `postgresql` to use Postgres via the explicit `DB_*` variables instead of `DATABASE_URL` | SQLite |

`RENDER_EXTERNAL_HOSTNAME` is set automatically by Render (not something you configure) and is appended to both `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` automatically — see `config/settings.py`.

If [`python-dotenv`](https://pypi.org/project/python-dotenv/) is installed (it's in `requirements.txt`), a local `.env` file is loaded automatically — this is optional, every setting also has an `os.environ` fallback.

## Security

- CSRF protection on every state-changing form (web) and DRF's session-auth CSRF checks (API)
- Every task/category view and API action re-checks ownership server-side (`user=request.user` / `IsOwner`) — never trusts an id in a URL
- Server-side validation via Django Forms and DRF Serializers (never relies on client-side JS alone)
- Passwords handled entirely by Django's auth system (PBKDF2 hashing, validators for length/similarity/common passwords)
- File uploads validated for extension and size before saving
- Secret key, debug flag, and allowed hosts are environment-driven — no secrets committed to source
- `DEBUG=False` automatically tightens cookie security settings (see `config/settings.py`)

## Testing

```bash
python manage.py test
```

Coverage includes:
- **Auth:** registration (incl. automatic Profile/Category creation), login, logout, protected-page redirects
- **Tasks:** create, edit, complete/reopen, pin, delete, search, filter (incl. Pinned), sort, pagination
- **Recurrence:** daily/weekly/monthly/custom math (including month-end clamping and year rollover), end-date cutoff, duplicate prevention, full view-flow integration
- **Categories:** create/rename/delete, duplicate-name rejection, delete-uncategorizes-tasks behavior
- **Calendar & Analytics:** correct task counts per day, correct stats after completions
- **Isolation (web):** one user can never view/edit/complete/pin/delete another user's tasks or categories via URL manipulation
- **API:** full CRUD, custom `complete`/`pin` actions, authentication requirements, and the same cross-user isolation (IDOR) checks against `/api/tasks/<id>/`

Before shipping, also run:

```bash
python manage.py check
python manage.py makemigrations --check   # confirms no model/migration drift
```

## Deployment Readiness

- `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and database settings are all environment-driven
- `STATIC_ROOT` is served in production by **WhiteNoise** (`whitenoise.middleware.WhiteNoiseMiddleware` + the `STORAGES["staticfiles"]` backend in `config/settings.py`) — `python manage.py collectstatic` hashes and compresses CSS/JS/icons so gunicorn can serve them itself, no separate static host needed
- **gunicorn** is the production WSGI server (`Procfile` / `render.yaml` both run `gunicorn config.wsgi:application`)
- Cookie security (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`) automatically tightens when `DEBUG=False`, and `SECURE_PROXY_SSL_HEADER` is set so Django correctly recognizes HTTPS requests behind Render's proxy
- Swapping to PostgreSQL is a configuration change only, via `DATABASE_URL` (see [Database](#database))
- **Known limitation — task attachment uploads are not persistent on Render's free/standard web service filesystem.** Render's disk is ephemeral: it's wiped on every deploy and on most restarts. `Task.attachment` (`tasks/models.py`) saves to local disk (`MEDIA_ROOT`) exactly as before — that part of the app is unchanged and still works for the lifetime of a running instance — but any uploaded file will be **lost** the next time the service redeploys or restarts. This project does **not** attempt to fix that automatically (no new paid storage service was wired in untested). If you need attachments to survive deploys, you have two options, neither implemented here:
  1. Add a [Render Disk](https://render.com/docs/disks) (persistent volume) mounted at `MEDIA_ROOT` — persists across deploys on that one instance, but doesn't work if you ever scale to multiple instances.
  2. Swap `DEFAULT_FILE_STORAGE` for an object-storage backend (e.g. `django-storages` + S3-compatible storage) — survives deploys and scales across instances, but needs its own account/bucket and credentials, which is a deliberate choice to leave to you rather than assume.

## Deploying to Render

### Prerequisites

- A [GitHub](https://github.com) account, with this project pushed to a repository you own
- A [Render](https://render.com) account
- Local Python matching `.python-version` (3.12.3) — not required to deploy, only to run the commands below yourself first

### 1. Run locally first

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py test
python manage.py createsuperuser
python manage.py runserver
```

Confirm the site works at `http://127.0.0.1:8000/` before deploying anything.

### 2. Push to GitHub

```bash
git init                      # skip if already a git repo
git add .
git commit -m "Prepare for Render deployment"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

### 3. Create the database on Render

Skip this step if you use the Blueprint in step 5 — it creates the database for you.

Manual path: Render dashboard → **New +** → **PostgreSQL** → give it a name (e.g. `todo-list-db`) → create. Once it's ready, copy its **Internal Database URL** — you'll paste that into `DATABASE_URL` in step 4.

### 4. Create the web service on Render

Manual path: Render dashboard → **New +** → **Web Service** → connect your GitHub repo.

| Field | Value |
|---|---|
| Runtime | Python 3 |
| Build Command | `./build.sh` |
| Start Command | `gunicorn config.wsgi:application` |

Then add these environment variables (Render dashboard → your service → **Environment**):

| Key | Value | Secret? |
|---|---|---|
| `DJANGO_SECRET_KEY` | generate one (e.g. `python -c "import secrets; print(secrets.token_urlsafe(50))"`) | **yes** — never commit this |
| `DJANGO_DEBUG` | `False` | no |
| `DJANGO_ALLOWED_HOSTS` | `.onrender.com` (or your custom domain once you have one) | no |
| `CSRF_TRUSTED_ORIGINS` | `https://*.onrender.com` | no |
| `DJANGO_TIME_ZONE` | `UTC` (or your preferred zone) | no |
| `DJANGO_SECURE_COOKIES` | `True` | no |
| `DATABASE_URL` | the Internal Database URL from step 3 | **yes** — contains a password |
| `PYTHON_VERSION` | `3.12.3` | no |

### 5. Or: deploy both at once with the Blueprint

Instead of steps 3–4, Render dashboard → **New +** → **Blueprint** → connect your repo → Render reads `render.yaml` and proposes the web service + database together, with `DJANGO_SECRET_KEY` auto-generated and `DATABASE_URL` wired automatically. Review the proposed plan (free tier availability depends on your account at the time) and click **Apply**.

Use one path or the other, not both — a service created from the Blueprint is managed by it, and editing the same settings by hand in the dashboard afterwards can conflict with what `render.yaml` declares.

### 6. Deploy and verify

Render runs `build.sh` (install deps → `collectstatic` → `migrate`) and then starts gunicorn. Once the deploy finishes:

1. Open the service's `*.onrender.com` URL.
2. Register an account and confirm the dashboard loads with CSS/icons/theme toggle working (confirms WhiteNoise is serving static files correctly).
3. Create a task, confirm it saves (confirms the database connection).
4. `python manage.py createsuperuser` **cannot** be run interactively on Render (no shell prompt). Use Render's dashboard → your service → **Shell** tab to run it there once, or set `DJANGO_SUPERUSER_*` environment variables and `createsuperuser --noinput` yourself if you prefer — this project does not create one automatically.

### Troubleshooting common errors

| Symptom | Likely cause |
|---|---|
| `DisallowedHost` error | The domain you're visiting isn't in `DJANGO_ALLOWED_HOSTS` — check for typos; Render's own hostname is added automatically, a custom domain is not |
| CSS/JS/icons missing (page loads but unstyled) | `collectstatic` didn't run — check the build log; confirm `WhiteNoiseMiddleware` is still listed right after `SecurityMiddleware` in `MIDDLEWARE` |
| `CSRF verification failed` on login/forms | `CSRF_TRUSTED_ORIGINS` missing the scheme (`https://`) or missing your actual domain |
| Redirect loop / "too many redirects" | Only relevant if you add `SECURE_SSL_REDIRECT` yourself — not set by default here; if you add it, `SECURE_PROXY_SSL_HEADER` (already set) must stay in place or Django never sees the request as secure |
| Build fails on `pip install` | Check the failing package/version in the build log against `requirements.txt` — Python version mismatches are the most common cause; confirm Render is actually using `.python-version` |
| Build succeeds, deploy fails on `migrate` | Check Render's **Logs** tab for the actual migration error — often a `DATABASE_URL` that doesn't match the database you created |
| Uploaded task attachments disappear after a deploy | Expected — see the persistence limitation above, not a bug |
| `ValueError: The file '...' could not be found with <...CompressedManifestStaticFilesStorage...>` when running locally (e.g. `python manage.py test` or `runserver` with `DJANGO_DEBUG=False`) | That storage backend only works once `python manage.py collectstatic` has written its manifest (`staticfiles/staticfiles.json`) — fine on Render, since `build.sh` always runs `collectstatic` before gunicorn starts. Locally, `config/settings.py` only switches to it when `DEBUG=False`; if you deliberately run with `DJANGO_DEBUG=False` locally, either run `python manage.py collectstatic` first or just leave `DJANGO_DEBUG=True` for local work (the default) |

### Deployment checklist

- [ ] `python manage.py test` passes locally
- [ ] `python manage.py check` reports no issues
- [ ] `.env` is **not** committed (confirm with `git status` — it's in `.gitignore`)
- [ ] Code pushed to GitHub
- [ ] Render Postgres database created (or using the Blueprint)
- [ ] Render web service created, pointed at your repo, build command `./build.sh`, start command `gunicorn config.wsgi:application`
- [ ] `DJANGO_SECRET_KEY` set to a real generated value (not the dev fallback)
- [ ] `DJANGO_DEBUG` set to `False`
- [ ] `DATABASE_URL` set (from the Render database, or via the Blueprint automatically)
- [ ] `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` cover your actual domain
- [ ] First deploy succeeded (check Render's **Logs** tab for `collectstatic` and `migrate` both completing)
- [ ] Site loads, register/login works, a task can be created
- [ ] Superuser created via Render's **Shell** tab if you need Django Admin access
- [ ] Understood and accepted the attachment-persistence limitation above (or already planned a Render Disk / object storage)

## Future Improvements

- Background email/push reminders (the `reminder_offset` field and `reminders_enabled` preference already model the intent; wiring up Celery + Redis for actual delivery was deliberately left out to avoid adding infrastructure the project doesn't otherwise need)
- Drag-and-drop task reordering
- Shareable/collaborative task lists
- A JS/mobile client built against the existing REST API
