from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UserReportAction(models.Model):
    class ActionChoices(models.TextChoices):
        CLAIMED = "claimed", "Claimed"
        WARNING = "warning", "Warning"
        BLOCKED = "blocked", "Blocked"
        UNBLOCKED = "unblocked", "Unblocked"
        ESCALATED = "escalated", "Escalated"
        DISMISSED = "dismissed", "Dismissed"

    report = models.ForeignKey(
        "users.UserReport",
        on_delete=models.CASCADE,
        related_name="actions",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="user_report_actions",
        null=True,
        blank=True,
    )
    actor_role = models.CharField(max_length=20, blank=True, default="")
    action = models.CharField(max_length=16, choices=ActionChoices.choices)
    previous_status = models.CharField(max_length=16)
    new_status = models.CharField(max_length=16)
    note = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_report_actions"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["report", "-created_at"],
                name="user_report_action_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("User report actions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("User report actions are immutable.")

    def __str__(self):
        return f"{self.action} on report #{self.report_id}"
