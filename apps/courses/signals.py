from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Course, Lesson, Module


def _recompute_lessons_count(course_id: int) -> None:
    count = Lesson.objects.filter(
        module__course_id=course_id,
        module__is_deleted=False,
    ).count()
    Course.all_objects.filter(pk=course_id).exclude(
        lessons_count=count,
    ).update(lessons_count=count)


@receiver(post_save, sender=Lesson)
def lesson_saved(sender, instance: Lesson, **kwargs):
    _recompute_lessons_count(instance.module.course_id)


@receiver(post_delete, sender=Lesson)
def lesson_deleted(sender, instance: Lesson, **kwargs):
    _recompute_lessons_count(instance.module.course_id)


@receiver(post_save, sender=Module)
def module_saved(sender, instance: Module, **kwargs):
    _recompute_lessons_count(instance.course_id)


@receiver(post_delete, sender=Module)
def module_deleted(sender, instance: Module, **kwargs):
    _recompute_lessons_count(instance.course_id)
