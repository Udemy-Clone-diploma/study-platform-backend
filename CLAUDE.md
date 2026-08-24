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

# Resolve parallel migration leaves (e.g. two PRs added 0007_*)
python manage.py makemigrations --merge --no-input

# Seed demo data for local dev (idempotent; safe to re-run)
python manage.py seed
```

## Architecture

**Stack**: Django 6.0.4 + Django REST Framework 3.17.1, PostgreSQL, JWT auth via `djangorestframework-simplejwt`.

**App layout** (`apps/`):
- `users/`: custom User model (email-based login, 4 roles: student/teacher/moderator/admin), JWT auth, email verification, password reset, role-specific profile models (`StudentProfile`, `TeacherProfile`, `ModeratorProfile`)
- `courses/`: `Course`, `Category`, `Tag`, `PricingPlan`, `Cohort` models with CRUD endpoints, filtering, and status choices. Pricing is per-plan, not on `Course`. Also hosts the wishlist endpoints (`/courses/wishlist/`, `/courses/<slug>/wishlist/`) and the per-role catalog views (`/courses/my-courses/` for teachers, `/courses/enrolled/` for students).
- `curriculum/`: `Module` and `Lesson` models (moved out of `courses` via `SeparateDatabaseAndState`) plus `GET /courses/<slug>/lessons/<id>/` detail endpoint with preview / enrollment access control. Owns the `lessons_count` recompute signal.
- `enrollments/`: `Enrollment` through-model (`StudentProfile` ↔ `Course`) with access-status lifecycle (active/pending/expired/revoked), `EnrollmentViewSet` for CRUD by students and admins, plus the signals that recompute `Course.students_count`.
- `reviews/`: `Review` model, paginated `GET` / authenticated `POST /courses/<slug>/reviews/`, and the signal that recomputes `Course.rating_avg` + `Course.rating_count`.
- `cart/`: shopping `Cart` / `CartItem` (item references a course's `PricingPlan` / `Cohort`). Uses a flat module layout (`models.py`, `views.py`, `services.py`), NOT the package-per-class convention the other apps follow.
- `payments/`: Stripe checkout — `Order`/`OrderItem`, `Payment`/`PaymentItem`/`PaymentAttempt`, `PaymentInstallment`, `Refund`, `WebhookEvent`. `StripeWebhookView` is mounted at the project root (`/webhook`), not under `/api/v1/`.
- `homework/`: `HomeworkAssignment` (FK to `User`); pairs with the `homework_graded` notification type.
- `notifications/`: `Notification` + `NotificationPreference`. All sends route through `NotificationService.create` (one recipient) / `fan_out` (many), gated per-recipient on channel prefs (`in_app` / `email`) whose defaults live in `apps/notifications/preferences.py`. `apps/notifications/signals.py` fans events out (e.g. `new_lesson` on `Lesson` create).
- `chat/`: real-time chat over WebSockets (Django Channels / ASGI, NOT plain DRF). `ChatConsumer` (`consumers.py`) handles the socket; `apps/chat/routing.py` maps `ws/chat/`; JWT auth on the socket lives in `apps/chat/middleware.py`. Chat's HTTP-side endpoints (history, moderation, reports) mount under `/api/v1/` via `apps/chat/urls.py`. See the Realtime chat note below.
- `common/`: shared DRF utilities (e.g. `StandardResultsSetPagination`). Cross-app helpers go here, not inside a feature app. Also hosts the demo seeder (`apps/common/management/commands/seed.py`).

**Demo seeding**: `python manage.py seed` populates a fresh dev DB with every role (admin/teacher/moderator/student + profiles), courses spanning all `course_type` values and statuses (draft/review/needs_revision/published), pricing plans (group/individual, USD/EUR/UAH, installments), cohorts, modules/lessons (video + text, preview + locked, `meeting_url`), enrollments with progress, and reviews. It is idempotent (every row is `get_or_create` on a natural key) and lets the denormalization signals fill `lessons_count` / `students_count` / `rating_*` / `lessons_completed_count`, so it stays correct as those rules change. It is deliberately NOT wired into `post_migrate` (that would inject demo rows into prod and the test DB and slow the suite); run it manually after a schema reset: `python manage.py migrate && python manage.py seed`. When you add or rename a model field the seeder should populate, update `seed.py` in the same change.

**Shared utilities** (`apps/common/`): import these before reinventing — `ActiveManager` (single soft-delete manager), `parse_limit` + `MAX_TOP_N_LIMIT` (top-N `?limit=N` parser, raises `InvalidLimitError`), `absolute_media_url(field_file, request)` for ImageField/FileField URL building, `UUIDUploadTo("<prefix>")` for `upload_to` on file fields.

**API URL prefix**: All app endpoints mount under `/api/v1/` (see `config/urls.py`). Docs (`/api/docs/`) and schema (`/api/schema/`) are siblings, not under `/api/v1/`.

**Module layout**: One public class per file, re-exported from the package's `__init__.py`. Exceptions: choice classes nested inside their owner model, manager classes paired with their model.

**File naming**: two conventions, split by package, do not mix them within one package.
- `models/`, `views/`, `serializers/`: PascalCase, file named after the class it holds (`apps/courses/models/Course.py`). This is a deliberate departure from PEP 8, so ruff's `N999` (`invalid-module-name`) is silenced for these three directories in `pyproject.toml`.
- `services/`: snake_case per PEP 8 (`apps/courses/services/course_service.py`). `N999` stays ON here, so a stray PascalCase service fails CI.

Known deviations, do not treat as precedent: `apps/payments/` is snake_case throughout (all 18 modules, written that way from the start), and `apps/cart/` is flat rather than packaged. Both stay as they are; new apps follow the split above.

**Service layer pattern**: Business logic lives in `services/` within each app (e.g., `AuthService`, `CourseService`), not in views. Views are thin and delegate to services.

**Domain exceptions**: Services raise domain exceptions defined in `apps/<app>/exceptions.py` (e.g., `AuthenticationError`, `InvalidPricingError`), never DRF `ValidationError`. Views catch them and translate to HTTP responses. Each app has a base error class (`UsersError`, `CoursesError`) that all domain errors inherit from.

**`services/` directory holds services only**. Constants, message strings, token utilities, and exceptions live at the app root: `apps/<app>/messages.py`, `apps/<app>/tokens.py`, `apps/<app>/exceptions.py`. Do not put non-service modules under `services/`.

**Input validation in views**: Views validate `request.data` with a DRF serializer (`serializer.is_valid(raise_exception=True)`), then call the service with `serializer.validated_data`. Avoid ad-hoc `request.data.get(...)` plus manual 400 responses.

**Filtering**: `django_filters.FilterSet` classes live in `apps/<app>/filters.py`, wired to views via `filterset_class`.

**Pagination**: Project-wide default is `apps.common.pagination.StandardResultsSetPagination` (page_size=20, max 100, `?page=` and `?page_size=` query params). List endpoints return the standard DRF paginated envelope (`count`, `next`, `previous`, `results`).

**List endpoint pattern**: each browseable resource has two endpoints — `/<resource>/` paginated for browse, plus a sibling top-N (e.g. `/courses/new-courses/`, `/categories/featured/`, `/users/top-teachers/`) returning a raw list capped by `MAX_TOP_N_LIMIT`. Top-N is a standalone `APIView` (not a ViewSet action) and uses `apps.common.limits.parse_limit` for `?limit=N`.

**Auth flow**: Register → email verification token → `AuthService.verify_email()` → Login → `AuthService.login()` → JWT access + refresh token pair. Tokens sent as `Authorization: Bearer <token>` header. Refresh tokens are blacklisted on logout.

**Soft deletes**: Every domain model implements `is_deleted` plus `objects = ActiveManager()` (from `apps.common.managers`) filtering it out by default; `all_objects` exposes deleted rows when needed. The active manager must be declared first so reverse FK queries (`course.modules.all()`) inherit the filter automatically. Exception: per-user activity records (`TestAttempt`, `Note`) have NO `is_deleted`/`ActiveManager` and use hard deletes, unlike admin/teacher-authored content models (`Course`, `Module`, `Lesson`, `Test`, `Question`); the seeder also skips these per-user records.

**Soft-delete admin**: Models with `is_deleted` register with a `ModelAdmin` that uses `SoftDeleteAdminMixin` from `apps/courses/admin.py` (overrides `delete_model`/`delete_queryset` to flip `is_deleted` and uses `all_objects` in `get_queryset`). The bare `admin.site.register(Model)` would issue SQL `DELETE` and bypass soft-delete.

**ImageField/FileField uploads**: use `upload_to=UUIDUploadTo("<prefix>")` from `apps.common.files`. Closure factories break `makemigrations` ("Could not find function ..."); the `@deconstructible` class is migration-safe and names files `<prefix>/<uuid>.<ext>` so URLs change on overwrite (CDN-cache-safe regardless of storage backend).

**Taxonomy curation**: `Tag` and `Category` are admin-curated. Tags expose only a public list endpoint; tag create/update/delete happens through Django admin. Categories additionally expose administrator-only API CRUD (`POST /categories/`, `PATCH`/`DELETE /categories/<id>/` via `CategoryViewSet` + `CategoryService`): slug auto-generates from the name when omitted or blank, DELETE soft-deletes and returns 409 while non-deleted courses reference the category, and name/slug uniqueness validates against `all_objects` (case-insensitive for name) because the DB unique constraints span soft-deleted rows. `GET /categories/` is public, paginated, supports `?search=` (name/description icontains) and `?ordering=` (name, courses_count), and serializes an annotated `courses_count` (apply `CategoryService.annotate_courses_count` to any queryset feeding `CategorySerializer`; without the annotation the key is omitted, which is intentional for the category embedded in course payloads). `GET /categories/featured/` returns categories with a non-null `featured_order`, sorted by it (null means not featured; set or clear it via the admin PATCH). Category icons are frontend-owned, mapped by slug; there is deliberately no icon field. Teachers and students select from existing entries when creating or browsing courses, never propose new ones via the API.

**Permissions layout**: Role-only checks live in `apps/users/permissions.py` and are reusable across apps (`IsAdmin`, `IsTeacher`, `IsStudent`, `IsStudentOrAdmin`, `IsTeacherOrAdmin`, `IsAdminOrModerator`). Object-level checks that need a specific model live in that app's own `permissions.py`. Global default is `IsAuthenticated`; public endpoints opt in with explicit `[AllowAny]`.

**Profile lookup**: `UserSerializer.get_profile` and `UserService.update_profile` resolve a user's profile via `user.role` (`f"{role}_profile"` for the reverse accessor, `PROFILE_MODELS[role]`/`PROFILE_SERIALIZERS[role]` for the model and serializer). The `related_name` on each profile model's `OneToOneField` must equal `<role>_profile` exactly; rename one and both lookups break silently.

**Full name in serializers**: use `serializers.CharField(source="user.get_full_name", read_only=True)` (Django's `AbstractUser.get_full_name()`), not a `SerializerMethodField` that formats `first_name` + `last_name`.

**Service transform pipeline**: When a service applies multiple business rules before save, encode each as a private `_apply_<name>_rules(validated_data)` that mutates and returns the dict, then chain them in `create_*` / `update_*`.

**Throttling**: Use `ScopedRateThrottle` + `throttle_scope = "<name>"` on the view, with the rate defined under `DEFAULT_THROTTLE_RATES` in settings. Custom `AnonRateThrottle` subclasses only when behavior (not just rate) needs to change.

**Branches**: GitFlow prefixes only: `feature/`, `release/`, `hotfix/`, `bugfix/`. Use `feature/<name>` for refactors too; this project does not use `refactor/`, `chore/`, or other conventional-commit-style prefixes. Branch off `develop` and PR back into `develop`; `main` is a release pointer and lags far behind.

**PR merge style**: project preserves feature commits via merge commits — use `gh pr merge <n> --merge`, not `--squash`. For stacked PRs, after the parent merges, rebase the child onto fresh `develop`; redundant commits drop automatically via patch-id.

**Configuration**: Settings read from `.env` via `python-decouple`. See `.env.example` for required variables (DB credentials, `SECRET_KEY`, `FRONTEND_URL`, email SMTP settings).

**API docs**: Swagger UI at `/api/docs/`, OpenAPI schema at `/api/schema/` (powered by `drf-spectacular`). JWT auth: `SimpleJWTScheme.match_subclasses = True` is set in `UsersConfig.ready()` so `CustomJWTAuthentication` is matched. `GenericAPIView`/`ViewSet` subclasses are introspected automatically; plain `APIView` subclasses require per-method `@extend_schema`. Use class-level `@extend_schema(tags=["..."])` on every view class for Swagger grouping. `SerializerMethodField` return types resolve via plain Python type hints (`-> str | None`) — no `@extend_schema_field` needed unless you require a specific serializer schema. For role-dependent request bodies, use separate `GenericAPIView` subclasses each with their own `serializer_class` rather than `PolymorphicProxySerializer` (Swagger UI does not render `oneOf`/`anyOf` request bodies).

**CORS**: Configured via `django-cors-headers`; frontend expected at `localhost:3000` by default.

**Test settings**: `config/test_settings.py` overrides the main settings for the test runner (uses SQLite by default). `from config.settings import *` re-evaluates module-level `decouple.config(...)` calls at import time, so any env var required without a default in `settings.py` must also be set in `pr-checks.yml` `env:` (currently `SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) — adding a new no-default `config(...)` without updating the workflow breaks `python manage.py check` in CI.

**CI**: `.github/workflows/pr-checks.yml` runs Django system check, migration drift check, and the test suite on every PR. `.github/workflows/main.yml` builds and pushes a Docker image to ECR on push to `develop`.

**Tests layout**: Each app keeps its tests in an `apps/<app>/tests/` package: `_factories.py` for shared fixtures, one `test_<feature>.py` per feature area. Tests are DRF `APITestCase` integration tests (no separate unit/service test layer) that spin up real DB rows and hit endpoints via `self.client`. The `make_course` factory in `apps/courses/tests/_factories.py` auto-sets `published_at=timezone.now()` whenever `status=PUBLISHED`, so any new test that needs a draft course must pass `status=Course.StatusChoices.DRAFT` explicitly.

**Signals**: App-level signal handlers live in `apps/<app>/signals.py` and are imported from the corresponding `AppConfig.ready()` so registration happens once on app load.

**Realtime chat (Channels / ASGI)**: `apps/chat/` serves WebSocket chat via Django Channels, so the project is ASGI, not just WSGI. `config/asgi.py` is a `ProtocolTypeRouter`: `http` goes to the normal Django app, `websocket` is wrapped `AllowedHostsOriginValidator` → `JWTAuthMiddleware` (`apps/chat/middleware.py`, authenticates the socket from a JWT since there is no session) → `URLRouter` over `apps/chat/routing.py` (`ws/chat/` → `ChatConsumer`). Cross-process message delivery uses the Redis **channel layer** (`CHANNEL_LAYERS` with `channels_redis`, pointed at `CHANNEL_REDIS_URL`/`REDIS_URL`), so a running Redis server is required to run chat — this is a *second, independent* use of Redis from the Celery broker, and removing Celery would not remove the Redis dependency. Installing `daphne` also changes `runserver`: it is replaced by the Channels dev server, which serves both HTTP and WS and logs requests as `HTTP GET /path 200 [time, client:port]`. Prod runs `daphne` for the same reason (see Production image).

**Async email + fan-out (Celery)**: notification work runs off the request path in `apps/notifications/tasks.py`, which holds three `@shared_task`s: `send_notification_email` (one recipient, used by `NotificationService.create`), `send_notification_emails` (many recipients, batched via Django `send_mass_mail` over one SMTP connection with one envelope per address, used by `NotificationService.fan_out`), and `fan_out_new_lesson` (recipient query + row creation + email batch for a new lesson). The `Lesson` `post_save` handler in `apps/notifications/signals.py` gates on published then enqueues `fan_out_new_lesson.delay(lesson.id)` via `transaction.on_commit`, so the worker only runs once the row is committed; a test that adds a lesson and asserts on the fan-out must wrap the create in `self.captureOnCommitCallbacks(execute=True)` or the task never fires under the rolled-back test transaction. Celery app is `config/celery.py` (imported in `config/__init__.py`, so every `manage.py` run requires `celery` installed). Broker is Redis (`CELERY_BROKER_URL`, default `redis://localhost:6379/0`; `redis://redis:6379/0` in the devcontainer). Tests run tasks inline via `CELERY_TASK_ALWAYS_EAGER` in `config/test_settings.py` — no broker/worker needed for the suite. Run a worker: `celery -A config worker -l info`. NOTE: the `redis` pip package is only the client; the Redis *server* runs as the `redis` service in `.devcontainer/my-setup/docker-compose.yml` (NOT installed by `setup.sh`), and the devcontainer compose lives there, not at the repo root.

**Notification retention**: `apps/notifications/management/commands/prune_notifications.py` hard-deletes read notifications older than a window (default `DEFAULT_RETENTION_DAYS = 90`, override with `--days N`); unread rows are always kept. `Notification` has no soft-delete and no delete signals, so it runs as a single hard DELETE. It is a management command because no Celery Beat is configured, and nothing schedules it yet.

**Deferred notification ops (AWS TODO)**: the off-request-path fan-out (`fan_out_new_lesson`) and batched emails (`send_notification_emails`) are built; what is left is deployment. A worker (`celery -A config worker`) must run in prod to drain the queue. Nothing schedules `prune_notifications` yet: wire it to run daily via an external scheduler (ECS scheduled task / EventBridge, or a k8s CronJob). There is no Celery Beat process, so any move to a Celery-scheduled prune would also need `celery -A config beat` deployed beside the worker.

**Enrollment writes**: The `StudentProfile.courses` M2M is read-only in practice. All enrollment creation must go through `EnrollmentService.create_enrollment` (or `Enrollment.objects.create(...)` for tests/admin). `student_profile.courses.add(...)` does a `bulk_create` on the through-model which **does not fire `post_save`**, so denormalized `Course.students_count` would silently drift. The previous `m2m_changed` patch for this was removed to keep one write path.

**Catalog ordering**: `CourseViewSet.list` filters to `status=PUBLISHED` and orders by `-published_at` by default. Exception: administrators get an all-status queryset (built on `Course.all_objects` because soft delete sets `status=archived` + `is_deleted=True`, minus internal `pending_edit` shadow drafts) and an admin-only `?status=a,b` filter in `CourseFilter.filter_status`; both are silently inert for every other caller. Any code path that creates a published course must populate `published_at` (the test factory does this automatically; service code should too).

**Catalog price annotation**: `CourseListSerializer` reads `price` / `currency` from `min_price` / `min_currency` annotations, not `Course` columns (the flat pricing fields were dropped in favor of `PricingPlan`). Any view feeding a `Course` queryset into `CourseListSerializer` (`CourseViewSet`, top-N endpoints, `TeacherCoursesView`, `EnrolledCoursesView`, `WishlistListView`, future list-shaped views) must first call `CourseService.annotate_min_price(qs)` or the catalog price serializes as `null`. The service-layer queryset builders (`get_teacher_courses_queryset`, `get_enrolled_courses_queryset`, `get_new_courses`, `get_popular_courses`) already apply this; `WishlistService.get_wishlisted_courses` too.

**Pricing plans**: `PricingPlan` is a child of `Course` (`related_name="pricing_plans"`) with `kind` (group / individual), `price`, `currency` (USD / EUR / UAH), and optional installment fields. Unique constraint on `(course, kind)`. Endpoints are nested under the course: `GET / POST /courses/<slug>/pricing-plans/`, `GET / PATCH / DELETE /courses/<slug>/pricing-plans/<id>/`. Reads follow course visibility; writes require course ownership or admin. `PricingPlanService.validate_installment_fields` enforces installment math (both or neither, `count >= 2`, `amount > 0`, `count * amount >= price`); duplicate `(course, kind)` returns 409 via `DuplicatePricingKindError`.

**Cohorts**: `Cohort` captures schedule and audience info per course (`duration_months`, `hours_per_week_min/max`, `group_size`, `delivery_mode`, `start_date`). Endpoints mirror PricingPlan: nested under `courses/<slug>/cohorts/`. `CohortSerializer.validate` checks `hours_per_week_min <= hours_per_week_max`.

**Curriculum split**: `Module` and `Lesson` live in `apps/curriculum/`, not `apps/courses/`. The move was done with `migrations.SeparateDatabaseAndState`: db tables `modules` and `lessons` stayed put, only Django's app state moved. `Course.modules` still works as a reverse FK (the FK from `curriculum.Module` to `courses.Course`). `apps/curriculum/signals.py` owns the `lessons_count` recompute now; `apps/courses/signals.py` is gone and `apps/courses/apps.py` no longer imports signals. `LessonDetailView` at `GET /courses/<slug>/lessons/<id>/` enforces preview / enrollment access control via `EnrollmentService.is_enrolled` (also allowing admins, moderators, and the owning teacher). Per-lesson notes: `GET/PUT/DELETE /courses/<slug>/lessons/<id>/note/` (`NoteView`), one `Note` per `(user, lesson)`, auth-required + enrollment-gated; `PUT` upserts, `GET` 404s when no note exists.

**Course-scoped views helper**: PricingPlan / Cohort endpoints share `apps/courses/views/_course_scoped.py`. `get_course_for_request(view, slug)` resolves the course and 404s if the requester cannot see it (PUBLISHED, or admin / moderator / owner for non-public statuses). `ensure_can_modify_course(user, course)` raises `PermissionDenied` unless the user is the owning teacher or an administrator. Reuse these in any future course-scoped resource (e.g., a per-course attachments endpoint) before reinventing the access checks.

**Reviews**: One review per (course, student) (unique constraint). `POST /courses/<slug>/reviews/` requires the student to be currently enrolled (`EnrollmentService.is_enrolled`); not-enrolled returns 403, duplicate returns 409 via `ReviewAlreadyExistsError`. Reads are public on published courses. `apps/reviews/signals.py` recomputes `Course.rating_avg` and `Course.rating_count` on `post_save` and `post_delete` using a single `aggregate(avg, count)` query and `Course.all_objects.filter().update()` (skips recursive signals and `auto_now`).

**Production image**: `Dockerfile` runs `daphne` (ASGI) serving `config.asgi:application` on port 8000 — ASGI, not WSGI/gunicorn, because the app serves WebSockets via Channels (see Realtime chat). The entrypoint script `entrypoint.sh` waits for the DB (`nc` loop on `DB_HOST`/`DB_PORT`) then runs `collectstatic` at container start; it does NOT run `migrate`, so migrations must run as a separate deploy step (and build does not need a `SECRET_KEY`). Whitenoise serves `STATIC_ROOT` (`/app/staticfiles`) via `CompressedManifestStaticFilesStorage`.

**Denormalized Course fields**: `Course.lessons_count` is recomputed by `apps/curriculum/signals.py`; `Course.rating_avg` and `Course.rating_count` are recomputed by `apps/reviews/signals.py`; `Course.students_count` is recomputed by `apps/enrollments/signals.py`. All three use `Course.all_objects.filter(...).update(...)` (not `.save()`) to skip recursive signals and `auto_now`. To find what writes a denormalized Course field, grep across the whole repo, not just `apps/courses/`.

**Moving a model between apps**: use `migrations.SeparateDatabaseAndState(state_operations=[...], database_operations=[])` in both the source app (`DeleteModel`) and the destination app (`CreateModel`), with the destination migration depending on the source. DB tables (`db_table`) stay put; only Django's app state changes. See `apps/courses/migrations/0016_move_module_lesson_to_curriculum.py` + `apps/curriculum/migrations/0001_initial.py` for the exact shape.
