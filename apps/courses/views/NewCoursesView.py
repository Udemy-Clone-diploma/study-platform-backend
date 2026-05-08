from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import InvalidLimitError
from apps.common.limits import parse_limit
from apps.courses.constants import DEFAULT_NEW_COURSES_LIMIT
from apps.courses.serializers import CourseListSerializer
from apps.courses.services.course_service import CourseService


class NewCoursesView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Courses"],
        parameters=[OpenApiParameter("limit", int, description="Max number of courses to return.")],
        responses={200: CourseListSerializer(many=True), 400: {"type": "object"}},
    )
    def get(self, request):
        try:
            limit = parse_limit(request, default=DEFAULT_NEW_COURSES_LIMIT)
        except InvalidLimitError as e:
            return Response({"limit": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        courses = CourseService.get_new_courses(limit=limit, context={"request": request})
        return Response(courses)
