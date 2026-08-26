from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course
from apps.enrollments.exceptions import (
    ActiveEnrollmentRequiredError,
    LessonNotInCourseError,
)
from apps.enrollments.services import ProgressService


@extend_schema(tags=["Progress"])
class LessonOpenedView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request, slug: str, lesson_id: int):
        course = Course.objects.filter(
            slug=slug,
            status=Course.StatusChoices.PUBLISHED,
        ).first()
        if course is None:
            raise NotFound("Course not found.")
        try:
            ProgressService.record_lesson_opened(request.user, course, lesson_id)
        except ActiveEnrollmentRequiredError:
            return Response(
                {"detail": "Active enrollment required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except LessonNotInCourseError:
            return Response(
                {"detail": "Lesson not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
