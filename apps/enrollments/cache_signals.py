from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.common.cache import invalidate_cache_on_commit
from apps.courses.models import Course
from apps.curriculum.cache import invalidate_lesson_for_user
from apps.curriculum.models import Lesson, Module, Question, Test, TestAttempt
from apps.enrollments.cache import (
    invalidate_course_progress_for_course,
    invalidate_course_progress_for_user,
)
from apps.enrollments.models import CourseCompletion, Enrollment, LessonCompletion
from apps.homework.models import (
    HomeworkAssignment,
    HomeworkAssignmentRecipient,
    HomeworkSubmission,
)


def _invalidate_user_progress(user_id: int | None, course_id: int | None) -> None:
    if user_id is not None and course_id is not None:
        invalidate_course_progress_for_user(user_id, course_id)


@receiver(pre_save, sender=Enrollment)
def remember_previous_enrollment_scope(sender, instance: Enrollment, **kwargs):
    if not instance.pk:
        instance._previous_cache_scope = None
        return
    instance._previous_cache_scope = (
        sender.all_objects.filter(pk=instance.pk)
        .values_list("student_profile__user_id", "course_id")
        .first()
    )


@receiver([post_save, post_delete], sender=Enrollment)
def enrollment_progress_changed(sender, instance: Enrollment, **kwargs):
    current_scope = (
        instance.student_profile.user_id,
        instance.course_id,
    )
    scopes = {
        current_scope,
        getattr(instance, "_previous_cache_scope", None),
    }
    for scope in scopes:
        if scope:
            invalidate_cache_on_commit(_invalidate_user_progress, *scope)


@receiver([post_save, post_delete], sender=LessonCompletion)
def lesson_completion_progress_changed(sender, instance: LessonCompletion, **kwargs):
    invalidate_cache_on_commit(
        _invalidate_user_progress,
        instance.enrollment.student_profile.user_id,
        instance.enrollment.course_id,
    )


@receiver([post_save, post_delete], sender=CourseCompletion)
def course_completion_progress_changed(sender, instance: CourseCompletion, **kwargs):
    invalidate_cache_on_commit(
        _invalidate_user_progress,
        instance.student_profile.user_id,
        instance.course_id,
    )


@receiver([post_save, post_delete], sender=TestAttempt)
def test_attempt_progress_changed(sender, instance: TestAttempt, **kwargs):
    user_id = instance.student_profile.user_id
    course_id = instance.test.module.course_id
    invalidate_cache_on_commit(
        _invalidate_user_progress,
        user_id,
        course_id,
    )
    lesson_ids = tuple(
        instance.test.lesson_items.values_list("lesson_id", flat=True).distinct()
    )
    for lesson_id in lesson_ids:
        invalidate_cache_on_commit(
            invalidate_lesson_for_user,
            lesson_id,
            user_id,
        )


@receiver([post_save, post_delete], sender=HomeworkAssignmentRecipient)
@receiver([post_save, post_delete], sender=HomeworkSubmission)
def homework_user_progress_changed(sender, instance, **kwargs):
    enrollment = instance.enrollment
    invalidate_cache_on_commit(
        _invalidate_user_progress,
        enrollment.student_profile.user_id,
        enrollment.course_id,
    )


@receiver([post_save, post_delete], sender=HomeworkAssignment)
def homework_course_progress_changed(sender, instance: HomeworkAssignment, **kwargs):
    invalidate_cache_on_commit(
        invalidate_course_progress_for_course,
        instance.course_id,
    )


@receiver([post_save, post_delete], sender=Course)
def course_progress_content_changed(sender, instance: Course, **kwargs):
    invalidate_cache_on_commit(
        invalidate_course_progress_for_course,
        instance.pk,
    )


@receiver([post_save, post_delete], sender=Module)
def module_progress_content_changed(sender, instance: Module, **kwargs):
    invalidate_cache_on_commit(
        invalidate_course_progress_for_course,
        instance.course_id,
    )


@receiver([post_save, post_delete], sender=Lesson)
def lesson_progress_content_changed(sender, instance: Lesson, **kwargs):
    invalidate_cache_on_commit(
        invalidate_course_progress_for_course,
        instance.module.course_id,
    )


@receiver([post_save, post_delete], sender=Test)
def test_progress_content_changed(sender, instance: Test, **kwargs):
    invalidate_cache_on_commit(
        invalidate_course_progress_for_course,
        instance.module.course_id,
    )


@receiver([post_save, post_delete], sender=Question)
def question_progress_content_changed(sender, instance: Question, **kwargs):
    invalidate_cache_on_commit(
        invalidate_course_progress_for_course,
        instance.test.module.course_id,
    )
