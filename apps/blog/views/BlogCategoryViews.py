from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.blog.exceptions import BlogCategoryInUseError
from apps.blog.models import BlogCategory
from apps.blog.serializers import BlogCategoryCreateUpdateSerializer, BlogCategorySerializer
from apps.blog.services.blog_category_service import BlogCategoryService
from apps.users.permissions import IsAdmin


@extend_schema(tags=["Blog"])
class BlogCategoryListCreateView(ListCreateAPIView):
    """GET /blog/categories/ — public list. POST — administrator-only: add a new category block."""

    queryset = BlogCategory.objects.all()
    pagination_class = None

    def get_serializer_class(self):
        return BlogCategoryCreateUpdateSerializer if self.request.method == "POST" else BlogCategorySerializer

    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "POST" else [AllowAny()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = BlogCategoryService.create_category(serializer.validated_data)
        return Response(BlogCategorySerializer(category).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Blog"])
class BlogCategoryDetailView(APIView):
    """PATCH/DELETE /blog/categories/{slug}/ — administrator-only edit/remove of a category block."""

    permission_classes = [IsAdmin]

    def patch(self, request, slug):
        category = get_object_or_404(BlogCategory.objects, slug=slug)
        serializer = BlogCategoryCreateUpdateSerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = BlogCategoryService.update_category(category, serializer.validated_data)
        return Response(BlogCategorySerializer(category).data)

    def delete(self, request, slug):
        category = get_object_or_404(BlogCategory.objects, slug=slug)
        try:
            BlogCategoryService.delete_category(category)
        except BlogCategoryInUseError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
