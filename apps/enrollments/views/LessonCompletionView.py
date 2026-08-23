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
    MandatoryTestNotPassedError,
)
from apps.enrollments.serializers import LessonCompletionResultSerializer
from apps.enrollments.services import ProgressService


def _get_published_course(slug: str) -> Course:
    course = Course.objects.filter(
        slug=slug,
        status=Course.StatusChoices.PUBLISHED,
    ).first()
    if course is None:
        raise NotFound("Course not found.")
    return course


@extend_schema(tags=["Progress"])
class LessonCompletionView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LessonCompletionResultSerializer

    @extend_schema(
        request=None,
        responses={200: LessonCompletionResultSerializer},
    )
    def post(self, request, slug: str, lesson_id: int):
        course = _get_published_course(slug)
        try:
            payload = ProgressService.mark_lesson_complete(
                request.user,
                course,
                lesson_id,
            )
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
        except MandatoryTestNotPassedError:
            return Response(
                {"detail": "You must pass this lesson's test before marking it complete."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            LessonCompletionResultSerializer(payload).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=None,
        responses={200: LessonCompletionResultSerializer},
    )
    def delete(self, request, slug: str, lesson_id: int):
        course = _get_published_course(slug)
        try:
            payload = ProgressService.unmark_lesson_complete(
                request.user,
                course,
                lesson_id,
            )
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
        return Response(
            LessonCompletionResultSerializer(payload).data,
            status=status.HTTP_200_OK,
        )
