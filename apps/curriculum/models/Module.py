from django.db import models

from apps.common.managers import ActiveManager
from apps.courses.models import Course


class Module(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField()

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="modules",
    )

    # Set only on a pending-edit draft course's modules: points back at the live
    # module this one was cloned from, so approval can merge changes in place.
    source_module = models.ForeignKey(
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
        db_table = "modules"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "order"],
                condition=models.Q(is_deleted=False),
                name="unique_active_module_order_per_course",
            ),
            models.UniqueConstraint(
                fields=["source_module"],
                condition=models.Q(source_module__isnull=False),
                name="unique_source_module",
            ),
        ]

    def __str__(self):
        return self.title
