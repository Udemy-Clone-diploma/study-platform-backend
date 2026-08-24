from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from apps.common.cache import invalidate_cache_on_commit
from apps.curriculum.cache import invalidate_lesson_content
from apps.curriculum.models import (
    Lesson,
    LessonDocument,
    LessonItem,
    Question,
    Test,
)


def _test_lesson_ids(test_id: int) -> tuple[int, ...]:
    return tuple(
        LessonItem.all_objects.filter(test_id=test_id)
        .values_list("lesson_id", flat=True)
        .distinct()
    )


def _invalidate_lessons(lesson_ids: tuple[int, ...]) -> None:
    for lesson_id in lesson_ids:
        invalidate_lesson_content(lesson_id)


@receiver([post_save, post_delete], sender=Lesson)
def lesson_content_changed(sender, instance: Lesson, **kwargs):
    invalidate_cache_on_commit(invalidate_lesson_content, instance.pk)


@receiver(pre_save, sender=LessonItem)
@receiver(pre_save, sender=LessonDocument)
def remember_previous_lesson(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_cache_lesson_id = None
        return
    instance._previous_cache_lesson_id = (
        sender.objects.filter(pk=instance.pk).values_list("lesson_id", flat=True).first()
    )


@receiver([post_save, post_delete], sender=LessonItem)
@receiver([post_save, post_delete], sender=LessonDocument)
def lesson_relation_changed(sender, instance, **kwargs):
    lesson_ids = {
        instance.lesson_id,
        getattr(instance, "_previous_cache_lesson_id", None),
    }
    for lesson_id in lesson_ids:
        if lesson_id is not None:
            invalidate_cache_on_commit(invalidate_lesson_content, lesson_id)


@receiver(pre_delete, sender=Test)
def remember_deleted_test_lessons(sender, instance: Test, **kwargs):
    instance._cache_lesson_ids = _test_lesson_ids(instance.pk)


@receiver(pre_delete, sender=Question)
def remember_deleted_question_lessons(sender, instance: Question, **kwargs):
    instance._cache_lesson_ids = _test_lesson_ids(instance.test_id)


@receiver([post_save, post_delete], sender=Test)
def test_content_changed(sender, instance: Test, **kwargs):
    lesson_ids = getattr(instance, "_cache_lesson_ids", None)
    if lesson_ids is None:
        lesson_ids = _test_lesson_ids(instance.pk)
    invalidate_cache_on_commit(_invalidate_lessons, lesson_ids)


@receiver([post_save, post_delete], sender=Question)
def question_content_changed(sender, instance: Question, **kwargs):
    lesson_ids = getattr(instance, "_cache_lesson_ids", None)
    if lesson_ids is None:
        lesson_ids = _test_lesson_ids(instance.test_id)
    invalidate_cache_on_commit(_invalidate_lessons, lesson_ids)
