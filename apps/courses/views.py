from rest_framework import filters, mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from apps.courses.constants import (
    DEFAULT_FEATURED_CATEGORIES_LIMIT,
    DEFAULT_NEW_COURSES_LIMIT,
    DEFAULT_POPULAR_COURSES_LIMIT,
    MAX_TOP_N_LIMIT,
)
from apps.courses.exceptions import InvalidLimitError, InvalidPricingError
from apps.courses.filters import CourseFilter
from apps.courses.models import Category, Course
from apps.courses.serializers import (
    CategorySerializer,
    CourseCreateUpdateSerializer,
    CourseDetailSerializer,
    CourseListSerializer,
)
from apps.courses.services.course_service import CourseService


def _parse_limit(request: Request, default: int) -> int:
    raw = request.query_params.get("limit")
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise InvalidLimitError("limit must be a positive integer")
    if value <= 0:
        raise InvalidLimitError("limit must be a positive integer")
    return min(value, MAX_TOP_N_LIMIT)


class CategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class CourseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Course.objects.select_related(
        "teacher_profile__user",
        "moderator_profile",
        "category",
    ).prefetch_related("tags")
    http_method_names = ["get", "post", "patch", "delete"]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = CourseFilter
    ordering_fields = ["price", "students_count", "rating_avg", "created_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return CourseListSerializer
        if self.action in {"create", "partial_update"}:
            return CourseCreateUpdateSerializer
        return CourseDetailSerializer

    def create(self, request, *args, **kwargs):
        try:
            data = CourseService.create_course_from_data(
                request.data,
                context=self.get_serializer_context(),
            )
        except InvalidPricingError as e:
            return Response({"price": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        course = self.get_object()
        try:
            data = CourseService.update_course_from_data(
                course,
                request.data,
                context=self.get_serializer_context(),
            )
        except InvalidPricingError as e:
            return Response({"price": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data)

    def destroy(self, request, *args, **kwargs):
        course = self.get_object()
        CourseService.soft_delete_course(course)
        return Response(status=status.HTTP_204_NO_CONTENT)


class NewCoursesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            limit = _parse_limit(request, default=DEFAULT_NEW_COURSES_LIMIT)
        except InvalidLimitError as e:
            return Response({"limit": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        courses = CourseService.get_new_courses(limit=limit)
        return Response(courses)


class PopularCoursesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            limit = _parse_limit(request, default=DEFAULT_POPULAR_COURSES_LIMIT)
        except InvalidLimitError as e:
            return Response({"limit": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        courses = CourseService.get_popular_courses(limit=limit)
        return Response(courses)


class FeaturedCategoriesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            limit = _parse_limit(request, default=DEFAULT_FEATURED_CATEGORIES_LIMIT)
        except InvalidLimitError as e:
            return Response({"limit": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        categories = CourseService.get_categories(limit=limit)
        return Response(categories)
