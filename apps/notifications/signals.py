from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.courses.models import Course
from apps.curriculum.models import Lesson
from apps.notifications.tasks import fan_out_new_lesson


@receiver(post_save, sender=Lesson)
def lesson_created(sender, instance: Lesson, created: bool, **kwargs):
    """Enqueue the `new_lesson` fan-out for a lesson added to a published course.

    There is no separate publish step on lessons; a lesson becoming available is
    its creation inside a published course, so that is the trigger. The fan-out
    itself (recipient query, row creation, email batch) runs in `fan_out_new_lesson`
    off the request path. `transaction.on_commit` guarantees the worker only runs
    once the lesson row is committed and visible.
    """
    if not created:
        return

    if instance.module.course.status != Course.StatusChoices.PUBLISHED:
        return

    transaction.on_commit(lambda: fan_out_new_lesson.delay(instance.id))
