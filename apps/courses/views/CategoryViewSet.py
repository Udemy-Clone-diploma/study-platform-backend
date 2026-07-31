from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.cache import cache_get_or_set, jittered_cache_timeout
from apps.common.serializers import MessageSerializer
from apps.courses.cache import public_category_list_cache_key
from apps.courses.exceptions import CategoryInUseError
from apps.courses.filters import CategoryFilter
from apps.courses.models import Category
from apps.courses.serializers import (
    CategorySerializer,
    CategoryWriteSerializer,
    PublicCategorySerializer,
)
from apps.courses.services import CategoryService
from apps.users.models import User
from apps.users.permissions import IsAdmin


@extend_schema(tags=["Categories"])
class CategoryViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    http_method_names = ["get", "post", "patch", "delete"]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = CategoryFilter
    ordering_fields = ["name_en", "courses_count"]
    ordering = ["name_en"]

    def get_queryset(self):
        queryset = Category.objects.all()
        if self.action == "list" and not self._is_admin_request():
            return CategoryService.annotate_public_courses_count(queryset)
        return CategoryService.annotate_courses_count(queryset)

    def get_permissions(self):
        if self.action == "list":
            return [AllowAny()]
        return [IsAdmin()]

    def get_serializer_class(self):
        if self.action == "list" and not self._is_admin_request():
            return PublicCategorySerializer
        # Retrieve is admin-only and loads every locale value for the edit form.
        if self.action in ("create", "partial_update", "retrieve"):
            return CategoryWriteSerializer
        return CategorySerializer

    def _is_admin_request(self) -> bool:
        user = self.request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == User.RoleChoices.ADMINISTRATOR
        )

    def list(self, request, *args, **kwargs):
        if self._is_admin_request():
            return super().list(request, *args, **kwargs)

        key = public_category_list_cache_key(request)

        def build_payload():
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data).data
            return self.get_serializer(queryset, many=True).data

        data = cache_get_or_set(
            key,
            build_payload,
            timeout=jittered_cache_timeout(
                settings.PUBLIC_CATEGORY_CACHE_TIMEOUT,
                settings.CACHE_TTL_JITTER_SECONDS,
            ),
        )
        return Response(data)

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
