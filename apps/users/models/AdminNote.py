from django.conf import settings
from django.db import models


class AdminNote(models.Model):
    """Internal admin bookkeeping about a user; never exposed to that user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_note",
    )
    content = models.TextField(max_length=2000)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"admin note on user {self.user_id}"
