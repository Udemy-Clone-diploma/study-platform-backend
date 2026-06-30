from django.conf import settings
from django.db import models

from .Lesson import Lesson


class Note(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_notes",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    content = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "lesson_notes"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lesson"],
                name="unique_note_per_user_lesson",
            ),
        ]

    def __str__(self):
        return f"note by {self.user_id} on lesson {self.lesson_id}"
