from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
    """Per-user channel overrides. Effective settings = defaults merged with these.

    Stored as a sparse override map (`{type: {channel: bool}}`) so adding a new
    notification type means extending the defaults constant, never a migration.
    See apps/notifications/preferences.py for defaults and resolution helpers.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
    )
    overrides = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_preferences"

    def __str__(self):
        return f"NotificationPreference: {self.user_id}"
