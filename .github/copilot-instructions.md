# Copilot Instructions — Backend

## Stack

Django 6 + Django REST Framework · Python 3.11+ · SQLite (dev) · python-decouple

## Commands (run from repo root)

```bash
python manage.py runserver            # Dev server → http://127.0.0.1:8000
python manage.py migrate              # Apply migrations
python manage.py makemigrations       # Generate migrations after model changes
python manage.py test <app_name>      # Run tests for a single app
python manage.py createsuperuser      # Create admin user
```

## Project Layout

```
config/       # Django project package — settings.py, urls.py, wsgi.py, asgi.py
manage.py
requirements.txt
.env.example  # Copy to .env and fill in SECRET_KEY and DEBUG
```

New apps live at repo root alongside `config/`. Register them in `config/settings.py` `INSTALLED_APPS` and wire their URLs in `config/urls.py`.

## Key Conventions

- **Environment variables** are read via `python-decouple`. Always use `config("KEY")` — never `os.environ` directly.
- **SECRET_KEY** must come from `.env`. Never commit it.
- `DEBUG` defaults to `False` if not set in `.env`.
- **REST endpoints** use DRF serializers + viewsets + routers. When adding a new app: create serializers, viewsets, and register a router in the app's `urls.py`, then include it in `config/urls.py`.
- **Migrations**: always run `makemigrations` + `migrate` after changing models.
