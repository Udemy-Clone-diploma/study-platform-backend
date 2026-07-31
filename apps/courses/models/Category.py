from django.db import models

from apps.common.managers import ActiveManager


class Category(models.Model):
    # name_en is the canonical/stable identifier (slug generation, uniqueness checks);
    # the other locales are optional and fall back to it when blank (apps.common.i18n).
    name_en = models.CharField(max_length=100, unique=True)
    name_uk = models.CharField(max_length=100, blank=True, default="")
    name_fr = models.CharField(max_length=100, blank=True, default="")
    name_es = models.CharField(max_length=100, blank=True, default="")
    name_de = models.CharField(max_length=100, blank=True, default="")
    slug = models.SlugField(unique=True)
    description_en = models.TextField(blank=True, default="")
    description_uk = models.TextField(blank=True, default="")
    description_fr = models.TextField(blank=True, default="")
    description_es = models.TextField(blank=True, default="")
    description_de = models.TextField(blank=True, default="")
    # Homepage curation: null means not featured, an integer is the display
    # position on /categories/featured/ (ascending, ties broken by name).
    featured_order = models.PositiveIntegerField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "categories"
        ordering = ["name_en"]
        verbose_name = "category"
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name_en
