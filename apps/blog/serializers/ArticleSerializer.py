from rest_framework import serializers

from apps.blog.models import Article, BlogCategory
from apps.blog.serializers.BlogCategorySerializer import BlogCategorySerializer
from apps.common.files import absolute_media_url
from apps.common.sanitize import sanitize_html


class ArticleAuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source="get_full_name")
    avatar = serializers.SerializerMethodField()
    role = serializers.CharField()

    def get_avatar(self, obj) -> str | None:
        return absolute_media_url(obj.avatar, self.context.get("request"))


class ArticleListSerializer(serializers.ModelSerializer):
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
        request = self.context.get("request")
        user = getattr(request, "user", None)
        moderator_profile = getattr(user, "moderator_profile", None) if user else None
        return bool(moderator_profile and obj.moderator_profile_id == moderator_profile.id)


class ArticleDetailSerializer(ArticleListSerializer):
    class Meta(ArticleListSerializer.Meta):
        fields = ArticleListSerializer.Meta.fields + ["body_html", "moderator_comment"]


class ArticleCreateUpdateSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=BlogCategory.objects.all(), required=False, allow_null=True,
    )

    class Meta:
        model = Article
        fields = ["title", "subtitle", "cover_image", "body_html", "category"]

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title is required.")
        return value

    def validate_body_html(self, value):
        return sanitize_html(value)
