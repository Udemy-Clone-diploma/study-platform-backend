from django.conf import settings
from django.db import models


class HomeworkAssignment(models.Model):
    class StatusChoices(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CLOSED = "closed", "Closed"

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="homework_assignments",
    )
    module = models.ForeignKey(
        "curriculum.Module",
        on_delete=models.SET_NULL,
        related_name="homework_assignments",
        null=True,
        blank=True,
    )
    lesson = models.ForeignKey(
        "curriculum.Lesson",
        on_delete=models.SET_NULL,
        related_name="homework_assignments",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_homework_assignments",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    due_at = models.DateTimeField(null=True, blank=True)
    max_score = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "homework_assignments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.course.title}: {self.title}"
