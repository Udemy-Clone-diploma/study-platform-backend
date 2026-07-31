from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.common.cache import invalidate_cache_on_commit
from apps.users.cache import (
    invalidate_public_top_teachers,
    invalidate_public_user_profile,
)
from apps.users.models import (
    ModeratorProfile,
    StudentProfile,
    TeacherProfile,
    User,
    UserReport,
)


@receiver([post_save, post_delete], sender=User)
def public_user_changed(sender, instance, **kwargs):
    invalidate_cache_on_commit(invalidate_public_user_profile, instance.pk)
    invalidate_cache_on_commit(invalidate_public_top_teachers)


@receiver([post_save, post_delete], sender=StudentProfile)
@receiver([post_save, post_delete], sender=TeacherProfile)
@receiver([post_save, post_delete], sender=ModeratorProfile)
def public_role_profile_changed(sender, instance, **kwargs):
    invalidate_cache_on_commit(invalidate_public_user_profile, instance.user_id)
    if isinstance(instance, TeacherProfile):
        invalidate_cache_on_commit(invalidate_public_top_teachers)


@receiver([post_save, post_delete], sender=UserReport)
def public_user_report_changed(sender, instance, **kwargs):
    invalidate_cache_on_commit(
        invalidate_public_user_profile,
        instance.reported_user_id,
    )
