from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "apps.users"

    def ready(self):
        from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme

        from . import cache_signals  # noqa: F401
        SimpleJWTScheme.match_subclasses = True
