from django.db import models

from apps.common.managers import ActiveManager

from .Module import Module


class Lesson(models.Model):
    title = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField()
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)

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
