from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.cache import cache_get_or_set, jittered_cache_timeout
from apps.common.exceptions import InvalidLimitError
from apps.common.limits import parse_limit
from apps.courses.cache import public_featured_categories_cache_key
from apps.courses.constants import DEFAULT_FEATURED_CATEGORIES_LIMIT
from apps.courses.serializers import PublicCategorySerializer
from apps.courses.services.course_service import CourseService


class FeaturedCategoriesView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Categories"],
        parameters=[
            OpenApiParameter("limit", int, description="Max number of categories to return.")
        ],
        responses={200: PublicCategorySerializer(many=True), 400: {"type": "object"}},
    )
    def get(self, request):
        try:
            limit = parse_limit(request, default=DEFAULT_FEATURED_CATEGORIES_LIMIT)
        except InvalidLimitError as e:
            return Response({"limit": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        categories = cache_get_or_set(
            public_featured_categories_cache_key(request, limit),
            lambda: CourseService.get_categories(
                limit=limit,
                context={"request": request},
            ),
            timeout=jittered_cache_timeout(
                settings.PUBLIC_CATEGORY_CACHE_TIMEOUT,
                settings.CACHE_TTL_JITTER_SECONDS,
            ),
        )
        return Response(categories)
