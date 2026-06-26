from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course
from apps.curriculum.models import Lesson
from apps.curriculum.serializers import LessonSerializer
from apps.enrollments.services import EnrollmentService
from apps.users.models import StudentProfile, User


@extend_schema(tags=["Lessons"])
class LessonDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=LessonSerializer)
    def get(self, request, slug: str, lesson_id: int):
        course = Course.objects.filter(
            slug=slug, status=Course.StatusChoices.PUBLISHED,
        ).first()
        if course is None:
            return Response(
                {"detail": "Course not found."}, status=status.HTTP_404_NOT_FOUND,
            )

        lesson = (
            Lesson.objects.filter(pk=lesson_id, module__course=course)
            .select_related("module")
            .prefetch_related("items", "documents")
            .first()
        )
        if lesson is None:
            return Response(
                {"detail": "Lesson not found."}, status=status.HTTP_404_NOT_FOUND,
            )

        # Teachers / staff see the full test (answers included); enrolled students get
        # answers hidden plus their own attempt status. Everyone else is read-only.
        is_privileged = self._is_privileged(request.user, course)
        student_profile = self._enrolled_student_profile(request.user, course)
        has_enrollment_access = is_privileged or student_profile is not None

        if not lesson.is_preview and not has_enrollment_access:
            return Response(
                {"detail": "Enrollment required to access this lesson."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            LessonSerializer(
                lesson,
                context={
                    "request": request,
                    "has_enrollment_access": has_enrollment_access,
                    "hide_answers": not is_privileged,
                    "student_profile": student_profile,
                },
            ).data
        )

    @staticmethod
    def _is_privileged(user, course: Course) -> bool:
        if not user or not user.is_authenticated:
            return False
        if user.role in (
            User.RoleChoices.ADMINISTRATOR,
            User.RoleChoices.MODERATOR,
        ):
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
