from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course
from apps.enrollments.exceptions import ActiveEnrollmentRequiredError
from apps.enrollments.serializers import CourseProgressSerializer
from apps.enrollments.services import ProgressService


@extend_schema(tags=["Progress"])
class CourseProgressView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CourseProgressSerializer)
    def get(self, request, slug: str):
        course = Course.objects.filter(
            slug=slug, status=Course.StatusChoices.PUBLISHED,
        ).first()
        if course is None:
            raise NotFound("Course not found.")
        try:
            payload = ProgressService.get_course_progress(request.user, course)
        except ActiveEnrollmentRequiredError:
            return Response(
                {"detail": "Active enrollment required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(CourseProgressSerializer(payload).data)
