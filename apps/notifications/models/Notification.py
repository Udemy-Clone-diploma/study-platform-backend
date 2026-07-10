from django.conf import settings
from django.db import models


class Notification(models.Model):
    class TypeChoices(models.TextChoices):
        NEW_MESSAGE = "new_message", "New message"
        HOMEWORK_GRADED = "homework_graded", "Homework graded"
        SCHEDULE_EVENT = "schedule_event", "Schedule event"
        NEW_LESSON = "new_lesson", "New lesson"
        COURSE_COMPLETED = "course_completed", "Course completed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=32, choices=TypeChoices.choices)
    title = models.CharField(max_length=255)
    body = models.CharField(max_length=512)
    link_url = models.CharField(max_length=512, null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    payload = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recipient", "is_read", "-created_at"],
                name="notif_recipient_read_created",
            ),
        ]

    def __str__(self):
        return f"{self.recipient_id}: {self.type} - {self.title}"
