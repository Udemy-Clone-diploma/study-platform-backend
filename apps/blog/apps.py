from django.apps import AppConfig


class BlogConfig(AppConfig):
    name = "apps.blog"

    def ready(self):
        from . import cache_signals  # noqa: F401
