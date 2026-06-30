from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.courses.models import Course
from apps.curriculum.models import Lesson
from apps.enrollments.models import Enrollment
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.users.models import User


@receiver(post_save, sender=Lesson)
def lesson_created(sender, instance: Lesson, created: bool, **kwargs):
    """Fan a `new_lesson` notification out to every student with active access.

    There is no separate publish step on lessons; a lesson becoming available
    is its creation inside a published course, so that is the trigger.
    """
    if not created:
        return

    course = instance.module.course
    if course.status != Course.StatusChoices.PUBLISHED:
        return

    recipient_ids = (
        Enrollment.objects.with_active_access()
        .filter(course_id=course.id)
        .values_list("student_profile__user_id", flat=True)
    )
    recipients = list(User.objects.filter(id__in=list(recipient_ids)))

    NotificationService.fan_out(
        recipients=recipients,
        type=Notification.TypeChoices.NEW_LESSON,
        title=course.title,
        body=f"New lesson published: {instance.title}",
        link_url=f"/learn/{course.slug}/{instance.id}",
        payload={
            "course_slug": course.slug,
            "lesson_id": instance.id,
            "module_id": instance.module_id,
        },
    )
