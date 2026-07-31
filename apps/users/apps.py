from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "apps.users"

    def ready(self):
        from . import cache_signals  # noqa: F401

        from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme
        SimpleJWTScheme.match_subclasses = True
