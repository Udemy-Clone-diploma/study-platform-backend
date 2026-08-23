from django.apps import AppConfig


class CoursesConfig(AppConfig):
    name = "apps.courses"

    def ready(self):
        from . import cache_signals  # noqa: F401
        from . import signals  # noqa: F401
