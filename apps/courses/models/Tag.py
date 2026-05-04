from django.db import models

from .ActiveTagManager import ActiveTagManager


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveTagManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "tags"
        ordering = ["name"]

    def __str__(self):
        return self.name
