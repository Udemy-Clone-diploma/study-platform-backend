from django.db import models

from apps.common.files import UUIDUploadTo
from apps.common.managers import ActiveManager

from .Module import Module


class Lesson(models.Model):
    class ContentTypeChoices(models.TextChoices):
        VIDEO = "video", "Video"
        TEXT = "text", "Text"

    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, default="")
    video = models.FileField(upload_to=UUIDUploadTo("lessons/videos"), null=True, blank=True)
    original_video_name = models.CharField(max_length=255, blank=True, default="")
    order = models.PositiveSmallIntegerField()
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    min_score = models.PositiveSmallIntegerField(null=True, blank=True)

    is_preview = models.BooleanField(default=False)

    content_type = models.CharField(
        max_length=10,
        choices=ContentTypeChoices.choices,
        default=ContentTypeChoices.VIDEO,
    )

    video_url = models.URLField(blank=True, null=True)

    body_html = models.TextField(blank=True, null=True)

    meeting_url = models.URLField(blank=True, null=True)

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="lessons",
    )

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "lessons"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["module", "order"],
                condition=models.Q(is_deleted=False),
                name="unique_active_lesson_order_per_module",
            ),
        ]

    def __str__(self):
        return self.title
