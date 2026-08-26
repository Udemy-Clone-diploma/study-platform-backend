from datetime import timedelta
from pathlib import Path

from decouple import config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1,host.docker.internal",
    cast=lambda v: [s.strip() for s in v.split(",")],
)


DJANGO_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

LOCAL_APPS = [
    "apps.common",
    "apps.users",
    "apps.courses",
    "apps.cart",
    "apps.curriculum",
    "apps.enrollments",
    "apps.certificates",
    "apps.homework",
    "apps.reviews",
    "apps.payments",
    "apps.schedule",
    "apps.notifications",
    "apps.chat",
    "apps.blog",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "channels",
    "django_filters",
    "corsheaders",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS + ["django_cleanup.apps.CleanupConfig"]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_USER_MODEL = "users.User"

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.users.authentication.CustomJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "email_verification": "5/hour",
        "password_reset": "5/hour",
        "user_report": "10/hour",
        "teacher_application": "5/hour",
        "teacher_application_check": "30/hour",
        "teacher_invitation_resend": "5/hour",
        "certificate_verify": "300/hour",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Study Platform API",
    "DESCRIPTION": "REST API for the Study Platform e-learning application.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "TAGS": [
        {
            "name": "Auth",
            "description": "Registration, login, logout, token refresh, email verification, password reset, and current-user endpoints.",
        },
        {"name": "Users", "description": "Admin user management and top teachers listing."},
        {"name": "User moderation", "description": "User report queues and moderation decisions."},
        {"name": "Courses", "description": "Course CRUD, new courses, and popular courses."},
        {"name": "Categories", "description": "Course category listing and featured categories."},
        {"name": "Cart", "description": "Student course cart operations."},
        {"name": "Enrollments", "description": "Course enrollment access records."},
        {"name": "Payments", "description": "Stripe checkout sessions and payment history."},
    ],
    "ENUM_NAME_OVERRIDES": {
        "UserLanguageEnum": "apps.users.models.User.LanguageChoices",
        "CourseLanguageEnum": "apps.courses.models.Course.LanguageChoices",
        "UserStatusEnum": "apps.users.models.User.StatusChoices",
        "CourseStatusEnum": "apps.courses.models.Course.StatusChoices",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24) if DEBUG else timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SECURE_BROWSER_XSS_FILTER = True # Включаем защиту от XSS атак (не даём вписывать скрипты в поля форм и т.д.)
X_FRAME_OPTIONS = "DENY" # Запрещаем отображение сайта в iframe (защита от кликджекинга)
SECURE_CONTENT_TYPE_NOSNIFF = True # Защита от MIME-атаки (не даём отправлять .exe файлы вместо изображений и т.д.)


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="eu-west-3")

if DEBUG:
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"
    DEFAULT_STORAGE_BACKEND = "django.core.files.storage.FileSystemStorage"
else:
    if not AWS_STORAGE_BUCKET_NAME:
        raise ImproperlyConfigured("AWS_STORAGE_BUCKET_NAME must be set when DEBUG=False.")
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    AWS_DEFAULT_ACL = None
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
    MEDIA_ROOT = ""
    DEFAULT_STORAGE_BACKEND = "storages.backends.s3.S3Storage"

STORAGES = {
    "default": {"BACKEND": DEFAULT_STORAGE_BACKEND},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

EMAIL_VERIFICATION_TIMEOUT = int(timedelta(days=2).total_seconds())

FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")

GOOGLE_OAUTH_CLIENT_ID = config("GOOGLE_OAUTH_CLIENT_ID", default="")

STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_CONNECT_WEBHOOK_SECRET = config("STRIPE_CONNECT_WEBHOOK_SECRET", default="")
STRIPE_CONNECT_COUNTRY = config("STRIPE_CONNECT_COUNTRY", default="US")
STRIPE_CONNECT_REFRESH_URL = config(
    "STRIPE_CONNECT_REFRESH_URL",
    default="http://localhost:3000/teacher-dashboard/payments?stripe=refresh",
)
STRIPE_CONNECT_RETURN_URL = config(
    "STRIPE_CONNECT_RETURN_URL",
    default="http://localhost:3000/teacher-dashboard/payments?stripe=return",
)
PLATFORM_COMMISSION_PERCENT = config("PLATFORM_COMMISSION_PERCENT", default="20.00")

LIQPAY_PUBLIC_KEY = config("LIQPAY_PUBLIC_KEY", default="")
LIQPAY_PRIVATE_KEY = config("LIQPAY_PRIVATE_KEY", default="")

LIQPAY_PAYOUT_MODE = config(
    "LIQPAY_PAYOUT_MODE",
    default="simulated",
)

LIQPAY_SIMULATED_PAYOUT_OUTCOME = config(
    "LIQPAY_SIMULATED_PAYOUT_OUTCOME",
    default="success",
)

LIQPAY_API_VERSION = config(
    "LIQPAY_API_VERSION",
    default=7,
    cast=int,
)

LIQPAY_API_URL = config(
    "LIQPAY_API_URL",
    default="https://www.liqpay.ua/api/request",
)

LIQPAY_HTTP_TIMEOUT = config(
    "LIQPAY_HTTP_TIMEOUT",
    default=10,
    cast=int,
)
LIQPAY_CHECKOUT_URL = config(
    "LIQPAY_CHECKOUT_URL",
    default="https://www.liqpay.ua/api/3/checkout",
)

LIQPAY_PAYOUT_SERVER_URL = config(
    "LIQPAY_PAYOUT_SERVER_URL",
    default="",
)
LIQPAY_SERVER_URL = config(
    "LIQPAY_SERVER_URL",
    default="",
)

LIQPAY_RESULT_URL = config(
    "LIQPAY_RESULT_URL",
    default=f"{FRONTEND_URL}/student-dashboard/payment?tab=history&liqpay=return",
)

INVOICE_COMPANY_NAME = config("INVOICE_COMPANY_NAME", default="Nexo4You")
INVOICE_COMPANY_EMAIL = config("INVOICE_COMPANY_EMAIL", default="")
INVOICE_COMPANY_ADDRESS = config("INVOICE_COMPANY_ADDRESS", default="")

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default=FRONTEND_URL,
    cast=lambda v: [s.strip() for s in v.split(",")],
)
CORS_ALLOW_CREDENTIALS = True

# DEBUG=True: emails print to terminal. DEBUG=False: real SMTP required.
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or "noreply@localhost"

REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")

# Django application cache. Keep it on a separate Redis database so clearing
# cached API data cannot remove Celery broker data or Channels state.
CACHE_URL = config(
    "CACHE_URL",
    default=f"{REDIS_URL.rsplit('/', 1)[0]}/1",
)
CACHE_DEFAULT_TIMEOUT = config(
    "CACHE_DEFAULT_TIMEOUT",
    default=300,
    cast=int,
)
CACHE_TTL_JITTER_SECONDS = config(
    "CACHE_TTL_JITTER_SECONDS",
    default=60,
    cast=int,
)
CACHE_STAMPEDE_LOCK_TIMEOUT = config(
    "CACHE_STAMPEDE_LOCK_TIMEOUT",
    default=10,
    cast=int,
)
CACHE_STAMPEDE_WAIT_TIMEOUT = config(
    "CACHE_STAMPEDE_WAIT_TIMEOUT",
    default=2,
    cast=float,
)
CACHE_STAMPEDE_POLL_INTERVAL = config(
    "CACHE_STAMPEDE_POLL_INTERVAL",
    default=0.05,
    cast=float,
)
PUBLIC_COURSE_LIST_CACHE_TIMEOUT = config(
    "PUBLIC_COURSE_LIST_CACHE_TIMEOUT",
    default=CACHE_DEFAULT_TIMEOUT,
    cast=int,
)
PUBLIC_COURSE_DETAIL_CACHE_TIMEOUT = config(
    "PUBLIC_COURSE_DETAIL_CACHE_TIMEOUT",
    default=600,
    cast=int,
)
PUBLIC_CATEGORY_CACHE_TIMEOUT = config(
    "PUBLIC_CATEGORY_CACHE_TIMEOUT",
    default=600,
    cast=int,
)
PUBLIC_USER_PROFILE_CACHE_TIMEOUT = config(
    "PUBLIC_USER_PROFILE_CACHE_TIMEOUT",
    default=600,
    cast=int,
)
PUBLIC_LESSON_CACHE_TIMEOUT = config(
    "PUBLIC_LESSON_CACHE_TIMEOUT",
    default=600,
    cast=int,
)
COURSE_PROGRESS_CACHE_TIMEOUT = config(
    "COURSE_PROGRESS_CACHE_TIMEOUT",
    default=60,
    cast=int,
)
CACHE_KEY_PREFIX = config("CACHE_KEY_PREFIX", default="study_platform")
CACHE_REDIS_SOCKET_TIMEOUT = config(
    "CACHE_REDIS_SOCKET_TIMEOUT",
    default=2,
    cast=float,
)
CACHE_REDIS_SOCKET_CONNECT_TIMEOUT = config(
    "CACHE_REDIS_SOCKET_CONNECT_TIMEOUT",
    default=2,
    cast=float,
)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": CACHE_URL,
        "TIMEOUT": CACHE_DEFAULT_TIMEOUT,
        "KEY_PREFIX": CACHE_KEY_PREFIX,
        "OPTIONS": {
            "socket_timeout": CACHE_REDIS_SOCKET_TIMEOUT,
            "socket_connect_timeout": CACHE_REDIS_SOCKET_CONNECT_TIMEOUT,
        },
    },
}

# Celery: notification emails are dispatched to a worker via this broker.
# Use redis://redis:6379/0 inside the devcontainer compose (see .env.example).
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_TASK_IGNORE_RESULT = True

CHANNEL_REDIS_URL = config("CHANNEL_REDIS_URL", default=REDIS_URL)
CHANNEL_REDIS_SOCKET_TIMEOUT = config(
    "CHANNEL_REDIS_SOCKET_TIMEOUT",
    default=10,
    cast=float,
)
CHANNEL_REDIS_SOCKET_CONNECT_TIMEOUT = config(
    "CHANNEL_REDIS_SOCKET_CONNECT_TIMEOUT",
    default=5,
    cast=float,
)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    "address": CHANNEL_REDIS_URL,
                    "socket_timeout": CHANNEL_REDIS_SOCKET_TIMEOUT,
                    "socket_connect_timeout": CHANNEL_REDIS_SOCKET_CONNECT_TIMEOUT,
                },
            ],
        },
    },
}

CHAT_MESSAGE_MAX_LENGTH = config("CHAT_MESSAGE_MAX_LENGTH", default=4000, cast=int)
CHAT_ATTACHMENT_MAX_BYTES = config(
    "CHAT_ATTACHMENT_MAX_BYTES",
    default=25 * 1024 * 1024,
    cast=int,
)
CHAT_ATTACHMENT_ALLOWED_TYPES = config(
    "CHAT_ATTACHMENT_ALLOWED_TYPES",
    default=(
        "image/jpeg,image/png,image/webp,image/gif,application/pdf,text/plain,application/zip"
    ),
    cast=lambda v: [item.strip() for item in v.split(",") if item.strip()],
)
# A single broker connection attempt must never stall a request: no retries on
# publish, no retries establishing the connection itself (kombu retries that
# separately from task-publish retries), and a tight socket timeout so an
# unreachable broker fails in ~1s instead of hanging (this matters a lot when
# fanning a notification out to many recipients in one request, e.g. a whole
# cohort).
CELERY_TASK_PUBLISH_RETRY = False
CELERY_BROKER_CONNECTION_RETRY = False
CELERY_BROKER_TRANSPORT_OPTIONS = {"socket_connect_timeout": 1, "socket_timeout": 1}
