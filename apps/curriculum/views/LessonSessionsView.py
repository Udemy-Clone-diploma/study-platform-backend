from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course
from apps.curriculum.models import Lesson
from apps.enrollments.services import EnrollmentService
from apps.schedule.models import Session
from apps.users.models import StudentProfile, User


@extend_schema(tags=["Lessons"])
class LessonSessionsView(APIView):
    """
    GET /courses/<slug>/lessons/<lesson_id>/sessions/

    Scheduled live sessions a teacher has tied to this lesson     """

    permission_classes = [AllowAny]

    def get(self, request, slug: str, lesson_id: int):
        course = Course.objects.filter(
            slug=slug, status=Course.StatusChoices.PUBLISHED,
        ).first()
        if course is None:
            return Response({"detail": "Course not found."}, status=status.HTTP_404_NOT_FOUND)

        lesson = Lesson.objects.filter(pk=lesson_id, module__course=course).first()
        if lesson is None:
            return Response({"detail": "Lesson not found."}, status=status.HTTP_404_NOT_FOUND)

        is_privileged = self._is_privileged(request.user, course)
        student_profile = self._enrolled_student_profile(request.user, course)

        if is_privileged:
            sessions = self._for_course(lesson, course)
        elif student_profile is not None:
            sessions = self._for_student(lesson, student_profile)
        else:
            return Response(
                {"detail": "Enrollment required to access this lesson."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response([
            {
                "id": s.id,
                "date": s.date.isoformat(),
                "start_time": s.start_time.strftime("%H:%M"),
                "end_time": s.end_time.strftime("%H:%M"),
                "meeting_link": s.meeting_link,
            }
            for s in sessions
        ])

    @staticmethod
    def _base(lesson):
        return (
            Session.objects.filter(lesson=lesson)
            .exclude(status=Session.Status.CANCELLED)
            .exclude(status=Session.Status.RESCHEDULED)
        )

    @classmethod
    def _for_course(cls, lesson, course):
        return (
            cls._base(lesson)
            .filter(
                Q(slot__delivery_format__course=course)
                | Q(schedule__cohort__course=course)
                | Q(course=course)
            )
            .order_by("date", "start_time")
            .distinct()
        )

    @classmethod
    def _for_student(cls, lesson, student_profile):
        return (
            cls._base(lesson)
            .filter(
                Q(student_profile=student_profile)
                | Q(cohort__members__enrollment__student_profile=student_profile)
                | Q(slot__booked_by__student_profile=student_profile)
                | Q(schedule__cohort__members__enrollment__student_profile=student_profile)
            )
            .order_by("date", "start_time")
            .distinct()
        )

    @staticmethod
    def _is_privileged(user, course: Course) -> bool:
        if not user or not user.is_authenticated:
            return False
        if user.role in (User.RoleChoices.ADMINISTRATOR, User.RoleChoices.MODERATOR):
            return True
        if user.role == User.RoleChoices.TEACHER:
            return course.teacher_profile.user_id == user.id
        return False

    @staticmethod
    def _enrolled_student_profile(user, course: Course) -> StudentProfile | None:
        if not user or not user.is_authenticated:
            return None
        if user.role != User.RoleChoices.STUDENT:
            return None
        try:
            student_profile = user.student_profile
        except StudentProfile.DoesNotExist:
            return None
        if EnrollmentService.student_has_course_access(student_profile, course):
            return student_profile
        return None