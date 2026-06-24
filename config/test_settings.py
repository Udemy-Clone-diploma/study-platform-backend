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
