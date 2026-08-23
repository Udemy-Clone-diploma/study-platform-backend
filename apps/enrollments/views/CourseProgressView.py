from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.cache import cache_get_or_set, jittered_cache_timeout
from apps.courses.models import Course
from apps.enrollments.cache import course_progress_cache_key
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
            # Access remains a live DB check. A stale cache entry must never
            # preserve access after an enrollment expires or is revoked.
            ProgressService.get_active_enrollment(request.user, course)
        except ActiveEnrollmentRequiredError:
            return Response(
                {"detail": "Active enrollment required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        def build_payload():
            payload = ProgressService.get_course_progress(request.user, course)
            payload.update(ProgressService.get_test_stats(request.user, course))
            payload.update(ProgressService.get_homework_stats(request.user, course))
            payload.update(ProgressService.get_completion_eligibility(request.user, course))
            return CourseProgressSerializer(payload).data

        data = cache_get_or_set(
            course_progress_cache_key(
                user_id=request.user.pk,
                course_id=course.pk,
            ),
            build_payload,
            timeout=jittered_cache_timeout(
                settings.COURSE_PROGRESS_CACHE_TIMEOUT,
                settings.CACHE_TTL_JITTER_SECONDS,
            ),
        )
        return Response(data)
