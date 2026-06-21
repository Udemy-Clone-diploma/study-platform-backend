from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.courses.models import Course
from apps.enrollments.models import Enrollment, LessonCompletion


def _active_enrollments_count(course_id: int) -> int:
    return Enrollment.objects.with_active_access().filter(course_id=course_id).count()


def _recompute_students_count(course_id: int | None) -> None:
    if course_id is None:
        return
    Course.all_objects.filter(pk=course_id).update(
        students_count=_active_enrollments_count(course_id)
    )


def _recompute_lessons_completed_count(enrollment_id: int | None) -> None:
    if enrollment_id is None:
        return
    count = LessonCompletion.objects.filter(enrollment_id=enrollment_id).count()
    Enrollment.all_objects.filter(pk=enrollment_id).update(
        lessons_completed_count=count,
    )


@receiver(pre_save, sender=Enrollment)
def remember_previous_course(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_course_id = None
        return
    instance._previous_course_id = (
        sender.objects.filter(pk=instance.pk)
        .values_list("course_id", flat=True)
        .first()
    )


@receiver(post_save, sender=Enrollment)
def update_students_count_on_save(sender, instance, **kwargs):
    _recompute_students_count(instance.course_id)
    previous_course_id = getattr(instance, "_previous_course_id", None)
    if previous_course_id != instance.course_id:
        _recompute_students_count(previous_course_id)


@receiver(post_delete, sender=Enrollment)
def update_students_count_on_delete(sender, instance, **kwargs):
    _recompute_students_count(instance.course_id)


@receiver(post_save, sender=LessonCompletion)
def lesson_completion_saved(sender, instance, **kwargs):
    _recompute_lessons_completed_count(instance.enrollment_id)


@receiver(post_delete, sender=LessonCompletion)
def lesson_completion_deleted(sender, instance, **kwargs):
    _recompute_lessons_completed_count(instance.enrollment_id)
