from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.constants import DEFAULT_POPULAR_COURSES_LIMIT
from apps.courses.exceptions import InvalidLimitError
from apps.courses.services.course_service import CourseService

from ._helpers import parse_limit


class PopularCoursesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            limit = parse_limit(request, default=DEFAULT_POPULAR_COURSES_LIMIT)
        except InvalidLimitError as e:
            return Response({"limit": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        courses = CourseService.get_popular_courses(limit=limit, context={"request": request})
        return Response(courses)
