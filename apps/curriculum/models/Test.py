from django.db import models

from apps.common.managers import ActiveManager

from .Module import Module


class Test(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    passing_score = models.PositiveSmallIntegerField(default=70)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    allow_retakes = models.BooleanField(default=False)
    max_attempts = models.PositiveSmallIntegerField(null=True, blank=True)
    order = models.PositiveSmallIntegerField()

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="tests",
    )

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "tests"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["module", "order"],
                condition=models.Q(is_deleted=False),
                name="unique_active_test_order_per_module",
            ),
        ]

    def __str__(self):
        return self.title
