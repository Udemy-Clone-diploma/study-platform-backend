from django.apps import AppConfig


class EnrollmentsConfig(AppConfig):
    name = "apps.enrollments"

    def ready(self):
        from . import signals  # noqa: F401
