from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.common.cache import invalidate_cache_on_commit
from apps.courses.models import Course
from apps.reviews.cache import (
    invalidate_all_course_reviews,
    invalidate_course_reviews,
    invalidate_top_reviews,
)
from apps.reviews.models import Review
from apps.users.models import User

PUBLIC_USER_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "avatar",
        "role",
        "is_deleted",
        "is_blocked",
    }
)


@receiver([post_save, post_delete], sender=Review)
def public_review_changed(sender, instance: Review, **kwargs):
    invalidate_cache_on_commit(invalidate_top_reviews)
    invalidate_cache_on_commit(invalidate_course_reviews, instance.course_id)


@receiver([post_save, post_delete], sender=Course)
def reviewed_course_changed(sender, instance: Course, **kwargs):
    invalidate_cache_on_commit(invalidate_top_reviews)
    invalidate_cache_on_commit(invalidate_course_reviews, instance.pk)


@receiver([post_save, post_delete], sender=User)
def review_author_changed(sender, instance: User, update_fields=None, **kwargs):
    if update_fields is not None and not PUBLIC_USER_FIELDS.intersection(update_fields):
        return
    invalidate_cache_on_commit(invalidate_top_reviews)
    invalidate_cache_on_commit(invalidate_all_course_reviews)
