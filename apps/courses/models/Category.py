from django.db import models

from apps.common.managers import ActiveManager


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    # Homepage curation: null means not featured, an integer is the display
    # position on /categories/featured/ (ascending, ties broken by name).
    featured_order = models.PositiveIntegerField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "categories"
        ordering = ["name"]
        verbose_name = "category"
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name
