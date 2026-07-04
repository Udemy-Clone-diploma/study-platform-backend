from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course
from apps.enrollments.exceptions import (
    ActiveEnrollmentRequiredError,
    CourseAlreadyCompletedError,
    CourseNotEligibleForCompletionError,
)
from apps.enrollments.serializers import CourseCompletionSerializer
from apps.enrollments.services import ProgressService


@extend_schema(tags=["Progress"])
class CourseCompletionView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CourseCompletionSerializer

    @extend_schema(
        request=None,
        responses={201: CourseCompletionSerializer},
    )
    def post(self, request, slug: str):
        course = Course.objects.filter(
            slug=slug, status=Course.StatusChoices.PUBLISHED,
        ).first()
        if course is None:
            raise NotFound("Course not found.")
        try:
            completion = ProgressService.complete_course(request.user, course)
        except ActiveEnrollmentRequiredError:
            return Response(
                {"detail": "Active enrollment required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except CourseNotEligibleForCompletionError:
            return Response(
                {"detail": "You have not yet met this course's completion requirements."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except CourseAlreadyCompletedError:
            return Response(
                {"detail": "Course already completed."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            CourseCompletionSerializer(completion, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )