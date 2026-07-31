import os

# Tests always use local file storage and must not require production S3 settings.
os.environ["DEBUG"] = "True"

from config.settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST_USER = "test@example.com"
EMAIL_HOST_PASSWORD = "test-password"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

# Run Celery tasks inline (no broker/worker needed during tests).
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Django's TestCase rolls the database back between tests but leaves cache
# backends intact. Clear LocMem before every test so cached API responses cannot
# leak objects from a previous test transaction.
TEST_RUNNER = "apps.common.test_runner.CacheIsolatedDiscoverRunner"
