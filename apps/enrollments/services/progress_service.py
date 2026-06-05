from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.courses.models import Course
from apps.curriculum.models import Lesson
from apps.enrollments.exceptions import (
    ActiveEnrollmentRequiredError,
    LessonNotInCourseError,
)
from apps.enrollments.models import Enrollment, LessonCompletion
from apps.users.models import StudentProfile, User


class ProgressService:
    @staticmethod
    def _student_profile(user: User) -> StudentProfile | None:
        if not user or not user.is_authenticated:
            return None
        if user.role != User.RoleChoices.STUDENT:
            return None
        try:
            return user.student_profile
        except StudentProfile.DoesNotExist:
            return None

    @classmethod
    def get_active_enrollment(cls, user: User, course: Course) -> Enrollment:
        student_profile = cls._student_profile(user)
        if student_profile is None:
            raise ActiveEnrollmentRequiredError
        enrollment = (
            Enrollment.objects.with_active_access()
            .filter(student_profile=student_profile, course=course)
            .first()
        )
        if enrollment is None:
            raise ActiveEnrollmentRequiredError
        return enrollment

    @staticmethod
    def _resolve_lesson(course: Course, lesson_id: int) -> Lesson:
        lesson = Lesson.objects.filter(pk=lesson_id, module__course=course).first()
        if lesson is None:
            raise LessonNotInCourseError
        return lesson

    @classmethod
    @transaction.atomic
    def mark_lesson_complete(cls, user: User, course: Course, lesson_id: int) -> dict:
        enrollment = cls.get_active_enrollment(user, course)
        lesson = cls._resolve_lesson(course, lesson_id)
        try:
            completion = LessonCompletion.objects.create(
                enrollment=enrollment, lesson=lesson,
            )
        except IntegrityError:
            completion = LessonCompletion.objects.get(
                enrollment=enrollment, lesson=lesson,
            )
        enrollment.refresh_from_db(fields=["lessons_completed_count"])
        return {
            "lesson_id": lesson.id,
            "completed_at": completion.completed_at,
            "lessons_completed_count": enrollment.lessons_completed_count,
        }

    @classmethod
    @transaction.atomic
    def unmark_lesson_complete(cls, user: User, course: Course, lesson_id: int) -> dict:
        enrollment = cls.get_active_enrollment(user, course)
        lesson = cls._resolve_lesson(course, lesson_id)
        LessonCompletion.objects.filter(
            enrollment=enrollment, lesson=lesson,
        ).delete()
        enrollment.refresh_from_db(fields=["lessons_completed_count"])
        return {
            "lesson_id": lesson.id,
            "completed_at": None,
            "lessons_completed_count": enrollment.lessons_completed_count,
        }

    @classmethod
    @transaction.atomic
    def record_lesson_opened(cls, user: User, course: Course, lesson_id: int) -> None:
        enrollment = cls.get_active_enrollment(user, course)
        lesson = cls._resolve_lesson(course, lesson_id)
        Enrollment.objects.filter(pk=enrollment.pk).update(
            last_lesson_id=lesson.id,
            last_opened_at=timezone.now(),
        )

    @classmethod
    def get_course_progress(cls, user: User, course: Course) -> dict:
        enrollment = cls.get_active_enrollment(user, course)
        completed_lesson_ids = list(
            LessonCompletion.objects.filter(enrollment=enrollment)
            .order_by("lesson_id")
            .values_list("lesson_id", flat=True)
        )
        return {
            "enrollment_id": enrollment.id,
            "lessons_completed_count": enrollment.lessons_completed_count,
            "lessons_count": course.lessons_count,
            "completed_lesson_ids": completed_lesson_ids,
            "last_lesson_id": enrollment.last_lesson_id,
            "last_opened_at": enrollment.last_opened_at,
        }

    @staticmethod
    def review_threshold(total_lessons: int) -> int:
        if total_lessons <= 0:
            return 0
        # ceil(0.30 * total): 5-lesson course -> 2, 50-lesson course -> 15.
        return max(1, (total_lessons * 3 + 9) // 10)

    @classmethod
    def is_eligible_to_review(cls, enrollment: Enrollment, course: Course) -> bool:
        if course.lessons_count <= 0:
            return False
        return enrollment.lessons_completed_count >= cls.review_threshold(course.lessons_count)
