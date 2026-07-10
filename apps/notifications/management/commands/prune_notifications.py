"""Delete old, already-read notifications to bound table growth.

In-app notifications are fanned out one row per recipient, so the table grows
with (events x recipients). A read notification past the retention window carries
no value, so this command hard-deletes it. Unread rows are always kept.

    python manage.py prune_notifications            # default 90-day window
    python manage.py prune_notifications --days 30

Run it daily from whatever scheduler you deploy with (system cron, an ECS
scheduled task, or a Kubernetes CronJob). Notification has no soft-delete and no
delete signals, so the queryset delete is a single hard DELETE.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.models import Notification

DEFAULT_RETENTION_DAYS = 90


class Command(BaseCommand):
    help = "Delete read notifications older than the retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_RETENTION_DAYS,
            help=f"Retention window in days (default: {DEFAULT_RETENTION_DAYS}).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timedelta(days=days)

        deleted, _ = Notification.objects.filter(
            is_read=True, created_at__lt=cutoff
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Pruned {deleted} read notification(s) older than {days} day(s)."
            )
        )
