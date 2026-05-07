from django.db import models

from apps.common.managers import ActiveManager


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name
