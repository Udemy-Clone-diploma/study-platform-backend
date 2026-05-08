# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run development server
python manage.py runserver

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Run all tests
DJANGO_SETTINGS_MODULE=config.test_settings python manage.py test

# Run tests for a specific app
python manage.py test apps.users
python manage.py test apps.courses

# Verify no pending model changes (migration drift check)
python manage.py makemigrations --check --dry-run
```

## Architecture

**Stack**: Django 6.0.4 + Django REST Framework 3.17.1, PostgreSQL, JWT auth via `djangorestframework-simplejwt`.

**App layout** (`apps/`):
- `users/`: custom User model (email-based login, 4 roles: student/teacher/moderator/admin), JWT auth, email verification, password reset, role-specific profile models (`StudentProfile`, `TeacherProfile`, `ModeratorProfile`)
- `courses/`: Course, Category, Tag models with CRUD endpoints, filtering, and status/pricing choices
- `common/`: shared DRF utilities (e.g. `StandardResultsSetPagination`). Cross-app helpers go here, not inside a feature app.

**API URL prefix**: All app endpoints mount under `/api/v1/` (see `config/urls.py`). Docs (`/api/docs/`) and schema (`/api/schema/`) are siblings, not under `/api/v1/`.

**Module layout**: One public class per file. `models/`, `views/`, `serializers/`, and `services/` are packages: `apps/<app>/models/<ModelName>.py`, etc., re-exported from `__init__.py`. Exceptions: choice classes nested inside their owner model, manager classes paired with their model.

**Service layer pattern**: Business logic lives in `services/` within each app (e.g., `AuthService`, `CourseService`), not in views. Views are thin and delegate to services.

**Domain exceptions**: Services raise domain exceptions defined in `apps/<app>/exceptions.py` (e.g., `AuthenticationError`, `InvalidPricingError`), never DRF `ValidationError`. Views catch them and translate to HTTP responses. Each app has a base error class (`UsersError`, `CoursesError`) that all domain errors inherit from.

**`services/` directory holds services only**. Constants, message strings, token utilities, and exceptions live at the app root: `apps/<app>/messages.py`, `apps/<app>/tokens.py`, `apps/<app>/exceptions.py`. Do not put non-service modules under `services/`.

**Input validation in views**: Views validate `request.data` with a DRF serializer (`serializer.is_valid(raise_exception=True)`), then call the service with `serializer.validated_data`. Avoid ad-hoc `request.data.get(...)` plus manual 400 responses.

**Filtering**: `django_filters.FilterSet` classes live in `apps/<app>/filters.py`, wired to views via `filterset_class`.

**Pagination**: Project-wide default is `apps.common.pagination.StandardResultsSetPagination` (page_size=20, max 100, `?page=` and `?page_size=` query params). List endpoints return the standard DRF paginated envelope (`count`, `next`, `previous`, `results`).

**Auth flow**: Register → email verification token → `AuthService.verify_email()` → Login → `AuthService.login()` → JWT access + refresh token pair. Tokens sent as `Authorization: Bearer <token>` header. Refresh tokens are blacklisted on logout.

**Soft deletes**: Every domain model implements `is_deleted` plus an `Active*Manager` filtering it out by default; `all_objects` exposes deleted rows when needed. The active manager must be declared first so reverse FK queries (`course.modules.all()`) inherit the filter automatically.

**Soft-delete admin**: Models with `is_deleted` register with a `ModelAdmin` that uses `SoftDeleteAdminMixin` from `apps/courses/admin.py` (overrides `delete_model`/`delete_queryset` to flip `is_deleted` and uses `all_objects` in `get_queryset`). The bare `admin.site.register(Model)` would issue SQL `DELETE` and bypass soft-delete.

**Taxonomy curation**: `Tag` and `Category` are admin-curated. Only list endpoints are exposed publicly; create/update/delete happens through Django admin. Teachers and students select from existing entries when creating or browsing courses, never propose new ones via the API.

**Permissions layout**: Role-only checks live in `apps/users/permissions.py` and are reusable across apps. Object-level checks that need a specific model live in that app's own `permissions.py`. Global default is `IsAuthenticated`; public endpoints opt in with explicit `[AllowAny]`.

**Profile lookup**: `UserSerializer.get_profile` and `UserService.update_profile` resolve a user's profile via `user.role` (`f"{role}_profile"` for the reverse accessor, `PROFILE_MODELS[role]`/`PROFILE_SERIALIZERS[role]` for the model and serializer). The `related_name` on each profile model's `OneToOneField` must equal `<role>_profile` exactly; rename one and both lookups break silently.

**Service transform pipeline**: When a service applies multiple business rules before save, encode each as a private `_apply_<name>_rules(validated_data)` that mutates and returns the dict, then chain them in `create_*` / `update_*`.

**Throttling**: Use `ScopedRateThrottle` + `throttle_scope = "<name>"` on the view, with the rate defined under `DEFAULT_THROTTLE_RATES` in settings. Custom `AnonRateThrottle` subclasses only when behavior (not just rate) needs to change.

**Branches**: GitFlow prefixes only: `feature/`, `release/`, `hotfix/`, `bugfix/`. Use `feature/<name>` for refactors too; this project does not use `refactor/`, `chore/`, or other conventional-commit-style prefixes. Branch off `develop` and PR back into `develop`; `main` is a release pointer and lags far behind.

**Configuration**: Settings read from `.env` via `python-decouple`. See `.env.example` for required variables (DB credentials, `SECRET_KEY`, `FRONTEND_URL`, email SMTP settings).

**API docs**: Swagger UI at `/api/docs/`, OpenAPI schema at `/api/schema/` (powered by `drf-spectacular`).

**CORS**: Configured via `django-cors-headers`; frontend expected at `localhost:3000` by default.

**Test settings**: `config/test_settings.py` overrides the main settings for the test runner (uses SQLite by default).

**CI**: `.github/workflows/pr-checks.yml` runs Django system check, migration drift check, and the test suite on every PR. `.github/workflows/main.yml` builds and pushes a Docker image to ECR on push to `develop`.

**Tests layout**: Currently one `apps/<app>/tests.py` per app, written as DRF `APITestCase` integration tests (no separate unit/service test layer). Each test class spins up real DB rows and hits endpoints via `self.client`.

**Signals**: App-level signal handlers live in `apps/<app>/signals.py` and are imported from the corresponding `AppConfig.ready()` so registration happens once on app load.
