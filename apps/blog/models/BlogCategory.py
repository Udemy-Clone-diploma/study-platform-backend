from django.db import models

from apps.common.managers import ActiveManager


class BlogCategory(models.Model):
    """Blog categories (initial 8 seeded via migration), shown as section blocks on /blog.
    Only administrators may create/edit/delete them (see apps.blog.permissions.IsAdmin usage
    in ArticleViews) -- teachers/moderators just assign an existing one to their articles."""

    # name_en is the canonical/stable identifier (slug generation, uniqueness checks);
    # the other locales are optional and fall back to it when blank (apps.common.i18n).
    name_en = models.CharField(max_length=100, unique=True)
    name_uk = models.CharField(max_length=100, blank=True, default="")
    name_fr = models.CharField(max_length=100, blank=True, default="")
    name_es = models.CharField(max_length=100, blank=True, default="")
    name_de = models.CharField(max_length=100, blank=True, default="")
    slug = models.SlugField(unique=True)
    headline_en = models.CharField(max_length=200)
    headline_uk = models.CharField(max_length=200, blank=True, default="")
    headline_fr = models.CharField(max_length=200, blank=True, default="")
    headline_es = models.CharField(max_length=200, blank=True, default="")
    headline_de = models.CharField(max_length=200, blank=True, default="")
    description_en = models.TextField(blank=True, default="")
    description_uk = models.TextField(blank=True, default="")
    description_fr = models.TextField(blank=True, default="")
    description_es = models.TextField(blank=True, default="")
    description_de = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "blog_categories"
        ordering = ["order", "name_en"]
        verbose_name = "blog category"
        verbose_name_plural = "blog categories"

    def __str__(self):
        return self.name_en
