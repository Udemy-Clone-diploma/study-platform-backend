from django.db import models

from apps.common.managers import ActiveManager

from .Module import Module


class Lesson(models.Model):
    title = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField()
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    min_score = models.PositiveSmallIntegerField(null=True, blank=True)
    is_preview = models.BooleanField(default=False)
    meeting_url = models.URLField(blank=True, null=True)
    unlock_after_days = models.PositiveIntegerField(null=True, blank=True)
    requires_previous = models.BooleanField(default=False)
    is_manually_locked = models.BooleanField(default=False)
    is_mandatory = models.BooleanField(default=False)

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="lessons",
    )

    source_lesson = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="draft_copies",
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
            models.UniqueConstraint(
                fields=["source_lesson"],
                condition=models.Q(source_lesson__isnull=False),
                name="unique_source_lesson",
            ),
        ]

    def __str__(self):
        return self.title
