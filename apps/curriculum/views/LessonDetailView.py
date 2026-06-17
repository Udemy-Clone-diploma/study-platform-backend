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

        if not lesson.is_preview and not self._has_full_access(request.user, course):
            return Response(
                {"detail": "Enrollment required to access this lesson."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(LessonSerializer(lesson).data)

    @staticmethod
    def _has_full_access(user, course: Course) -> bool:
        if not user or not user.is_authenticated:
            return False
        if user.role in (
            User.RoleChoices.ADMINISTRATOR,
            User.RoleChoices.MODERATOR,
        ):
            return True
        if user.role == User.RoleChoices.TEACHER:
            return course.teacher_profile.user_id == user.id
        if user.role == User.RoleChoices.STUDENT:
            try:
                student_profile = user.student_profile
            except StudentProfile.DoesNotExist:
                return False
            return EnrollmentService.student_has_course_access(student_profile, course)
        return False
