from django.db import models

from apps.common.managers import ActiveManager


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "tags"
        ordering = ["name"]

    def __str__(self):
        return self.name
