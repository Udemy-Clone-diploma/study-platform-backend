from django.conf import settings
from django.db import models

from .Lesson import Lesson


class Note(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_notes",
    )
    # SET_NULL (not CASCADE): a student's note on a course they've already
    # finished must survive the teacher later deleting that lesson/course.
    # The snapshot fields below are what actually get displayed once lesson
    # is gone -- they're refreshed on every upsert_note() while lesson is
    # still live (see NoteService.upsert_note), then frozen.
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notes",
    )
    content = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    course_id = models.PositiveBigIntegerField(null=True, blank=True)
    course_slug = models.CharField(max_length=255, blank=True, default="")
    course_title = models.CharField(max_length=255, blank=True, default="")
    course_level = models.CharField(max_length=20, blank=True, default="")
    module_title = models.CharField(max_length=255, blank=True, default="")
    lesson_title = models.CharField(max_length=255, blank=True, default="")
    lesson_order = models.PositiveSmallIntegerField(null=True, blank=True)

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
