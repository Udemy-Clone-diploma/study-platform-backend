from django.core.management.base import BaseCommand, CommandError

from apps.common.cache import cache_is_available


class Command(BaseCommand):
    help = "Verify that the configured Django cache can write to and read from Redis."

    def handle(self, *args, **options):
        if not cache_is_available():
            raise CommandError("Redis cache is unavailable.")
        self.stdout.write(self.style.SUCCESS("Redis cache is available."))
