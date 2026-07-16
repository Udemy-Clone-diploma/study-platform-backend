from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.serializers import MessageSerializer
from apps.courses.exceptions import CategoryInUseError
from apps.courses.filters import CategoryFilter
from apps.courses.models import Category
from apps.courses.serializers import CategorySerializer
from apps.courses.services import CategoryService
from apps.users.permissions import IsAdmin


@extend_schema(tags=["Categories"])
class CategoryViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CategorySerializer
    http_method_names = ["get", "post", "patch", "delete"]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = CategoryFilter
    ordering_fields = ["name", "courses_count"]
    ordering = ["name"]

    def get_queryset(self):
        return CategoryService.annotate_courses_count(Category.objects.all())

    def get_permissions(self):
        if self.action == "list":
            return [AllowAny()]
        return [IsAdmin()]

    def _category_response(self, category, status_code=status.HTTP_200_OK):
        category.courses_count = category.courses.count()
        return Response(self.get_serializer(category).data, status=status_code)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = CategoryService.create_category(serializer.validated_data)
        return self._category_response(category, status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        category = self.get_object()
        serializer = self.get_serializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = CategoryService.update_category(category, serializer.validated_data)
        return self._category_response(category)

    @extend_schema(responses={204: None, 409: MessageSerializer})
    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        try:
            CategoryService.delete_category(category)
        except CategoryInUseError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
