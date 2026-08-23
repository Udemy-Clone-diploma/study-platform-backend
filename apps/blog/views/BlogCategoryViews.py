from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.blog.cache import public_blog_categories_cache_key
from apps.blog.exceptions import BlogCategoryInUseError
from apps.blog.models import BlogCategory
from apps.blog.serializers import BlogCategoryCreateUpdateSerializer, BlogCategorySerializer
from apps.blog.services.blog_category_service import BlogCategoryService
from apps.common.cache import cache_get_or_set, jittered_cache_timeout
from apps.users.permissions import IsAdmin


@extend_schema(tags=["Blog"])
class BlogCategoryListCreateView(ListCreateAPIView):
    """GET /blog/categories/: public list. POST: administrator-only, adds a category block."""

    pagination_class = None

    def get_queryset(self):
        return BlogCategoryService.annotate_articles_count(BlogCategory.objects.all())

    def get_serializer_class(self):
        return BlogCategoryCreateUpdateSerializer if self.request.method == "POST" else BlogCategorySerializer

    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "POST" else [AllowAny()]

    def list(self, request, *args, **kwargs):
        data = cache_get_or_set(
            public_blog_categories_cache_key(request),
            lambda: self.get_serializer(self.get_queryset(), many=True).data,
            timeout=jittered_cache_timeout(
                settings.CACHE_DEFAULT_TIMEOUT,
                settings.CACHE_TTL_JITTER_SECONDS,
            ),
        )
        return Response(data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = BlogCategoryService.create_category(serializer.validated_data)
        return Response(
            BlogCategoryCreateUpdateSerializer(category).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["Blog"])
class BlogCategoryDetailView(APIView):
    """GET/PATCH/DELETE /blog/categories/{slug}/: administrator-only.
    GET returns every locale field (not just the resolved one) so the admin
    edit form can populate all of them, unlike the public list endpoint."""

    permission_classes = [IsAdmin]

    def get(self, request, slug):
        category = get_object_or_404(BlogCategory.objects, slug=slug)
        return Response(BlogCategoryCreateUpdateSerializer(category).data)

    def patch(self, request, slug):
        category = get_object_or_404(BlogCategory.objects, slug=slug)
        serializer = BlogCategoryCreateUpdateSerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = BlogCategoryService.update_category(category, serializer.validated_data)
        return Response(BlogCategoryCreateUpdateSerializer(category).data)

    def delete(self, request, slug):
        category = get_object_or_404(BlogCategory.objects, slug=slug)

        resolution = request.data.get("resolution")
        move_to = None
        if resolution == "move":
            target_slug = request.data.get("target_category")
            if not target_slug or target_slug == slug:
                return Response(
                    {"detail": "Choose a different category to move the articles into."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            move_to = get_object_or_404(BlogCategory.objects, slug=target_slug)

        try:
            BlogCategoryService.delete_category(
                category,
                archive_articles=resolution == "archive",
                move_to=move_to,
            )
        except BlogCategoryInUseError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
