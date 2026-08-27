from rest_framework import serializers

from apps.blog.models import Article
from apps.blog.serializers.ArticleSerializer import ArticleAuthorSerializer
from apps.blog.serializers.BlogCategorySerializer import BlogCategorySerializer
from apps.common.files import absolute_media_url


class PublicArticleListSerializer(serializers.ModelSerializer):
    """Published article shape without moderation- or viewer-specific fields."""

    category = BlogCategorySerializer(read_only=True)
    author = ArticleAuthorSerializer(read_only=True)
    cover_image = serializers.SerializerMethodField()
    is_assigned_to_me = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "slug",
            "subtitle",
            "cover_image",
            "cover_crops",
            "category",
            "author",
            "status",
            "created_at",
            "updated_at",
            "published_at",
            "is_assigned_to_me",
        ]

    def get_cover_image(self, obj) -> str | None:
        return absolute_media_url(obj.cover_image, self.context.get("request"))

    def get_is_assigned_to_me(self, obj) -> bool:
        return False


class PublicArticleDetailSerializer(PublicArticleListSerializer):
    moderator_comment = serializers.SerializerMethodField()

    class Meta(PublicArticleListSerializer.Meta):
        fields = PublicArticleListSerializer.Meta.fields + [
            "body_html",
            "moderator_comment",
        ]

    def get_moderator_comment(self, obj) -> str:
        return ""
