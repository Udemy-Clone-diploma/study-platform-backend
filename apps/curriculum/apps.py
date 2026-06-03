from django.apps import AppConfig


class CurriculumConfig(AppConfig):
    name = "apps.curriculum"

    def ready(self):
        from . import signals  # noqa: F401
