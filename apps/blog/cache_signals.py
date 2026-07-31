from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.blog.cache import (
    invalidate_all_public_article_details,
    invalidate_public_article_detail,
    invalidate_public_article_lists,
    invalidate_public_blog_categories,
)
from apps.blog.models import Article, BlogCategory
from apps.common.cache import invalidate_cache_on_commit
from apps.users.models import User

PUBLIC_AUTHOR_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "avatar",
        "role",
        "is_deleted",
        "is_blocked",
    }
)


@receiver([post_save, post_delete], sender=Article)
def public_article_changed(sender, instance: Article, **kwargs):
    invalidate_cache_on_commit(invalidate_public_article_lists)
    invalidate_cache_on_commit(invalidate_public_article_detail, instance.pk)
    invalidate_cache_on_commit(invalidate_public_blog_categories)


@receiver([post_save, post_delete], sender=BlogCategory)
def public_blog_category_changed(sender, instance: BlogCategory, **kwargs):
    invalidate_cache_on_commit(invalidate_public_blog_categories)
    invalidate_cache_on_commit(invalidate_public_article_lists)
    invalidate_cache_on_commit(invalidate_all_public_article_details)


@receiver([post_save, post_delete], sender=User)
def public_article_author_changed(
    sender,
    instance: User,
    update_fields=None,
    **kwargs,
):
    if update_fields is not None and not PUBLIC_AUTHOR_FIELDS.intersection(update_fields):
        return
    invalidate_cache_on_commit(invalidate_public_article_lists)
    invalidate_cache_on_commit(invalidate_all_public_article_details)
