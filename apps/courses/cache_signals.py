from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_save,
)
from django.dispatch import receiver

from apps.common.cache import invalidate_cache_on_commit
from apps.courses.cache import (
    invalidate_public_courses,
    invalidate_public_courses_and_categories,
)
from apps.courses.models import (
    Category,
    Cohort,
    CohortMember,
    Course,
    CourseDeliveryFormat,
    PricingPlan,
    Tag,
)
from apps.curriculum.models import Lesson, Module
from apps.enrollments.models import Enrollment
from apps.reviews.models import Review
from apps.users.models import TeacherProfile, User

PUBLIC_ENROLLMENT_FIELDS = frozenset(
    {
        "course",
        "course_id",
        "delivery_format",
        "delivery_format_id",
        "access_status",
        "access_granted_at",
        "access_until",
        "is_deleted",
    }
)


@receiver([post_save, post_delete], sender=Course)
def course_changed(sender, instance, **kwargs):
    invalidate_cache_on_commit(invalidate_public_courses_and_categories)


@receiver([post_save, post_delete], sender=Category)
def category_changed(sender, instance, **kwargs):
    invalidate_cache_on_commit(invalidate_public_courses_and_categories)


@receiver([post_save, post_delete], sender=Tag)
def tag_changed(sender, instance, **kwargs):
    invalidate_cache_on_commit(invalidate_public_courses)


@receiver(m2m_changed, sender=Course.tags.through)
def course_tags_changed(sender, instance, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        invalidate_cache_on_commit(invalidate_public_courses)


@receiver([post_save, post_delete], sender=PricingPlan)
@receiver([post_save, post_delete], sender=CourseDeliveryFormat)
@receiver([post_save, post_delete], sender=Cohort)
@receiver([post_save, post_delete], sender=CohortMember)
@receiver([post_save, post_delete], sender=Module)
@receiver([post_save, post_delete], sender=Lesson)
@receiver([post_save, post_delete], sender=Review)
def public_course_relation_changed(sender, instance, **kwargs):
    invalidate_cache_on_commit(invalidate_public_courses)


@receiver(post_save, sender=Enrollment)
def enrollment_changed(sender, instance, created, update_fields, **kwargs):
    if (
        created
        or update_fields is None
        or PUBLIC_ENROLLMENT_FIELDS.intersection(update_fields)
    ):
        invalidate_cache_on_commit(invalidate_public_courses)


@receiver(post_delete, sender=Enrollment)
def enrollment_deleted(sender, instance, **kwargs):
    invalidate_cache_on_commit(invalidate_public_courses)


@receiver([post_save, post_delete], sender=TeacherProfile)
def teacher_profile_changed(sender, instance, **kwargs):
    invalidate_cache_on_commit(invalidate_public_courses)


@receiver(pre_save, sender=User)
def remember_previous_user_role(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_cache_role = None
        return
    instance._previous_cache_role = (
        sender.objects.filter(pk=instance.pk)
        .values_list("role", flat=True)
        .first()
    )


@receiver(post_save, sender=User)
def teacher_user_changed(sender, instance, **kwargs):
    if (
        instance.role == User.RoleChoices.TEACHER
        or getattr(instance, "_previous_cache_role", None)
        == User.RoleChoices.TEACHER
    ):
        invalidate_cache_on_commit(invalidate_public_courses)


@receiver(post_delete, sender=User)
def teacher_user_deleted(sender, instance, **kwargs):
    if instance.role == User.RoleChoices.TEACHER:
        invalidate_cache_on_commit(invalidate_public_courses)
