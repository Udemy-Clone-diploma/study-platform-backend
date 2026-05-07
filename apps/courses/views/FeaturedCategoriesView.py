from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import InvalidLimitError
from apps.common.limits import parse_limit
from apps.courses.constants import DEFAULT_FEATURED_CATEGORIES_LIMIT
from apps.courses.services.course_service import CourseService


class FeaturedCategoriesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            limit = parse_limit(request, default=DEFAULT_FEATURED_CATEGORIES_LIMIT)
        except InvalidLimitError as e:
            return Response({"limit": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        categories = CourseService.get_categories(limit=limit)
        return Response(categories)
