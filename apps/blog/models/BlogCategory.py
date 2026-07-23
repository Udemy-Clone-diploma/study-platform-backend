from django.db import models

from apps.common.managers import ActiveManager


class BlogCategory(models.Model):
    """Blog categories (initial 8 seeded via migration), shown as section blocks on /blog.
    Only administrators may create/edit/delete them (see apps.blog.permissions.IsAdmin usage
    in ArticleViews) -- teachers/moderators just assign an existing one to their articles."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    headline = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "blog_categories"
        ordering = ["order", "name"]
        verbose_name = "blog category"
        verbose_name_plural = "blog categories"

    def __str__(self):
        return self.name
