from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    name = "apps.reviews"

    def ready(self):
        from . import cache_signals  # noqa: F401
        from . import signals  # noqa: F401
