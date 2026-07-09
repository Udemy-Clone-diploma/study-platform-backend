import logging
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.courses.models import Course
from apps.curriculum.models import Lesson, LessonItem, Test, TestAttempt
from apps.enrollments.exceptions import (
    ActiveEnrollmentRequiredError,
    CourseAlreadyCompletedError,
    CourseCompletionRequiresTeacherError,
    CourseNotEligibleForCompletionError,
    LessonNotInCourseError,
    MandatoryTestNotPassedError,
)
from apps.enrollments.models import CourseCompletion, Enrollment, LessonCompletion
from apps.users.models import StudentProfile, User

logger = logging.getLogger(__name__)


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

    @staticmethod
    def _mandatory_test_id(lesson: Lesson) -> int | None:
        """The test a mandatory lesson requires passed before completion, if any."""
        if not lesson.is_mandatory:
            return None
        item = (
            LessonItem.objects.filter(
                lesson=lesson, item_type=LessonItem.ItemType.TEST, test__isnull=False,
            )
            .first()
        )
        return item.test_id if item else None

    @classmethod
    @transaction.atomic
    def mark_lesson_complete(cls, user: User, course: Course, lesson_id: int) -> dict:
        enrollment = cls.get_active_enrollment(user, course)
        lesson = cls._resolve_lesson(course, lesson_id)
        test_id = cls._mandatory_test_id(lesson)
        if test_id is not None and not TestAttempt.objects.filter(
            student_profile=enrollment.student_profile, test_id=test_id, passed=True,
        ).exists():
            raise MandatoryTestNotPassedError
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

    @classmethod
    def get_test_stats(cls, user: User, course: Course) -> dict:
        """
        Informational only — does NOT affect course completion """
        enrollment = cls.get_active_enrollment(user, course)
        return cls._test_stats_for_enrollment(enrollment, course)

    @staticmethod
    def _test_stats_for_enrollment(enrollment: Enrollment, course: Course) -> dict:
        passed = failed = skipped = 0
        scores = []

        tests = Test.objects.filter(
            module__course=course, lesson_items__is_deleted=False,
        ).distinct()
        for test in tests:
            latest = (
                TestAttempt.objects.filter(
                    student_profile=enrollment.student_profile, test=test,
                )
                .order_by("-attempt_number")
                .first()
            )
            if latest is None:
                skipped += 1
            elif latest.passed:
                passed += 1
                scores.append(latest.score)
            else:
                failed += 1
                scores.append(latest.score)

        average = round(sum(scores) / len(scores), 1) if scores else None
        return {
            "test_average": average,
            "tests_passed": passed,
            "tests_failed": failed,
            "tests_skipped": skipped,
            "tests_total": passed + failed + skipped,
        }

    @classmethod
    def get_homework_stats(cls, user: User, course: Course) -> dict:
        """
        Informational only — does NOT affect course completion. Homework only
        makes sense for a specific enrollment taught with a teacher  """
        enrollment = cls.get_active_enrollment(user, course)
        return cls._homework_stats_for_enrollment(enrollment)

    @staticmethod
    def _is_with_teacher_format(enrollment: Enrollment) -> bool:
        from apps.courses.models import CourseDeliveryFormat

        return (
            enrollment.delivery_format_id is not None
            and enrollment.delivery_format.format_type in (
                CourseDeliveryFormat.FormatType.INDIVIDUAL,
                CourseDeliveryFormat.FormatType.GROUP,
            )
        )

    @classmethod
    def _homework_stats_for_enrollment(cls, enrollment: Enrollment) -> dict:
        from apps.homework.models import HomeworkAssignmentRecipient, HomeworkSubmission

        is_with_teacher = cls._is_with_teacher_format(enrollment)

        total = HomeworkAssignmentRecipient.objects.filter(enrollment=enrollment).count()

        scores = list(
            HomeworkSubmission.objects.filter(
                enrollment=enrollment, score__isnull=False,
            ).values_list("score", flat=True)
        )
        graded = len(scores)
        average = round(sum(scores) / graded, 1) if scores else None
        return {
            "is_with_teacher": is_with_teacher,
            "homework_average": average,
            "homework_graded": graded,
            "homework_ungraded": max(0, total - graded),
            "homework_total": total,
        }

    @staticmethod
    def _completion_percent(enrollment: Enrollment, course: Course) -> int:
        if course.lessons_count <= 0:
            return 0
        return round(enrollment.lessons_completed_count * 100 / course.lessons_count)

    @staticmethod
    def _mandatory_lessons_done(enrollment: Enrollment, course: Course) -> bool:
        completed_lesson_ids = set(
            LessonCompletion.objects.filter(enrollment=enrollment).values_list(
                "lesson_id", flat=True,
            )
        )
        mandatory_ids = set(
            Lesson.objects.filter(
                module__course=course, is_mandatory=True,
            ).values_list("id", flat=True)
        )
        return mandatory_ids.issubset(completed_lesson_ids)

    @classmethod
    def get_completion_eligibility(cls, user: User, course: Course) -> dict:
        enrollment = cls.get_active_enrollment(user, course)
        is_completed = CourseCompletion.objects.filter(
            student_profile=enrollment.student_profile, course=course,
        ).exists()
        # Group/individual enrollments are finished by the teacher
        # (ProgressService.teacher_complete_course), never by the student.
        if cls._is_with_teacher_format(enrollment):
            return {"can_complete_course": False, "is_course_completed": is_completed}
        eligible = (
            course.lessons_count > 0
            and cls._completion_percent(enrollment, course) >= course.passing_score
            and cls._mandatory_lessons_done(enrollment, course)
        )
        return {
            "can_complete_course": eligible and not is_completed,
            "is_course_completed": is_completed,
        }

    @classmethod
    @transaction.atomic
    def complete_course(cls, user: User, course: Course) -> CourseCompletion:
        enrollment = cls.get_active_enrollment(user, course)
        if CourseCompletion.objects.filter(
            student_profile=enrollment.student_profile, course=course,
        ).exists():
            raise CourseAlreadyCompletedError

        if cls._is_with_teacher_format(enrollment):
            raise CourseCompletionRequiresTeacherError

        eligible = (
            course.lessons_count > 0
            and cls._completion_percent(enrollment, course) >= course.passing_score
            and cls._mandatory_lessons_done(enrollment, course)
        )
        if not eligible:
            raise CourseNotEligibleForCompletionError

        return cls._create_completion(enrollment, course, cls._resolve_final_score(enrollment, course))

    @classmethod
    @transaction.atomic
    def teacher_complete_course(cls, course: Course, enrollment: Enrollment) -> CourseCompletion:
        """Teacher-initiated completion, for delivery formats taught live
        (group/individual) where the course may have zero curriculum lessons,
        so `complete_course`'s lesson-progress eligibility can never pass."""
        if CourseCompletion.objects.filter(
            student_profile=enrollment.student_profile, course=course,
        ).exists():
            raise CourseAlreadyCompletedError

        if not cls._teacher_completion_eligible(course, enrollment):
            raise CourseNotEligibleForCompletionError

        return cls._create_completion(enrollment, course, cls._resolve_final_score(enrollment, course))

    @staticmethod
    def _teacher_completion_eligible(course: Course, enrollment: Enrollment) -> bool:
        from apps.homework.models import HomeworkAssignment, HomeworkSubmission

        has_assignments = HomeworkAssignment.objects.filter(
            course=course, status=HomeworkAssignment.StatusChoices.PUBLISHED,
        ).exists()
        if not has_assignments:
            return True
        return HomeworkSubmission.objects.filter(
            enrollment=enrollment, status=HomeworkSubmission.StatusChoices.REVIEWED,
        ).exists()

    @classmethod
    def _resolve_final_score(cls, enrollment: Enrollment, course: Course) -> Decimal | None:
        homework_stats = cls._homework_stats_for_enrollment(enrollment)
        if homework_stats["is_with_teacher"] and homework_stats["homework_average"] is not None:
            return Decimal(str(homework_stats["homework_average"]))
        test_average = cls._test_stats_for_enrollment(enrollment, course)["test_average"]
        return Decimal(str(test_average)) if test_average is not None else None

    @classmethod
    def _create_completion(
        cls, enrollment: Enrollment, course: Course, final_score: Decimal | None,
    ) -> CourseCompletion:
        order_item = None
        if enrollment.order_id:
            from apps.payments.models import OrderItem

            order_item = (
                OrderItem.objects.filter(order_id=enrollment.order_id, course=course)
                .select_related("order")
                .first()
            )

        completion = CourseCompletion.objects.create(
            student_profile=enrollment.student_profile,
            course=course,
            title=course.title,
            teacher_name=course.teacher_profile.user.get_full_name(),
            level=course.level,
            image_url=course.image.url if course.image else None,
            progress_percent=cls._completion_percent(enrollment, course),
            started_at=enrollment.access_granted_at,
            final_score=final_score,
            paid_amount=order_item.unit_amount if order_item else None,
            paid_currency=order_item.currency if order_item else "",
            purchased_at=order_item.order.completed_at if order_item else None,
        )

        if course.with_certificate:
            cls._attach_certificate(completion, course, enrollment.student_profile.user)

        return completion

    @classmethod
    def _attach_certificate(cls, completion: CourseCompletion, course: Course, user: User) -> None:
        from apps.enrollments.services.certificate_service import CertificateService

        try:
            pdf_bytes, thumbnail_bytes = CertificateService.render_certificate_assets(
                course=course, completion=completion, student_name=user.get_full_name(),
            )
        except Exception:
            logger.exception("Certificate generation failed for completion %s", completion.id)
            return

        completion.certificate_file.save(
            f"certificate-{completion.id}.pdf", ContentFile(pdf_bytes), save=False,
        )
        completion.certificate_thumbnail.save(
            f"certificate-{completion.id}.jpg", ContentFile(thumbnail_bytes), save=False,
        )
        completion.certificate_url = completion.certificate_file.url
        completion.save(update_fields=["certificate_file", "certificate_thumbnail", "certificate_url"])

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
