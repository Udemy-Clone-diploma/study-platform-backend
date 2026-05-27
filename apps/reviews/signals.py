from decimal import Decimal

from django.db.models import Avg, Count
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.courses.models import Course

from .models import Review


def _recompute_course_rating(course_id: int) -> None:
    aggregates = Review.objects.filter(course_id=course_id).aggregate(
        avg=Avg("rating"), total=Count("id"),
    )
    Course.all_objects.filter(pk=course_id).update(
        rating_avg=aggregates["avg"] or Decimal("0.00"),
        rating_count=aggregates["total"] or 0,
    )


@receiver(post_save, sender=Review)
def review_saved(sender, instance: Review, **kwargs):
    _recompute_course_rating(instance.course_id)


@receiver(post_delete, sender=Review)
def review_deleted(sender, instance: Review, **kwargs):
    _recompute_course_rating(instance.course_id)
