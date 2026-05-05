from django.apps import AppConfig


class CoursesConfig(AppConfig):
    name = "apps.courses"

    def ready(self):
        from . import signals  # noqa: F401
