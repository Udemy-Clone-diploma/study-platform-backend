from django.apps import AppConfig


class EnrollmentsConfig(AppConfig):
    name = "apps.enrollments"

    def ready(self):
        from . import cache_signals  # noqa: F401
        from . import signals  # noqa: F401
