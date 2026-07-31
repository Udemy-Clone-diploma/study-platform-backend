from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.cache import cache_get_or_set, jittered_cache_timeout
from apps.common.exceptions import InvalidLimitError
from apps.common.limits import parse_limit
from apps.courses.constants import DEFAULT_NEW_COURSES_LIMIT
from apps.courses.cache import public_new_courses_cache_key
from apps.courses.serializers import PublicCourseListSerializer
from apps.courses.services.course_service import CourseService


class NewCoursesView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Courses"],
        parameters=[OpenApiParameter("limit", int, description="Max number of courses to return.")],
        responses={200: PublicCourseListSerializer(many=True), 400: {"type": "object"}},
    )
    def get(self, request):
        try:
            limit = parse_limit(request, default=DEFAULT_NEW_COURSES_LIMIT)
        except InvalidLimitError as e:
            return Response({"limit": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        courses = cache_get_or_set(
            public_new_courses_cache_key(request, limit),
            lambda: CourseService.get_new_courses(
                limit=limit,
                context={"request": request},
            ),
            timeout=jittered_cache_timeout(
                settings.PUBLIC_COURSE_LIST_CACHE_TIMEOUT,
                settings.CACHE_TTL_JITTER_SECONDS,
            ),
        )
        return Response(courses)
