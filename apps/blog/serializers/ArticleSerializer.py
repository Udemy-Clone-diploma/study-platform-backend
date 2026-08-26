import json

from rest_framework import serializers

from apps.blog.models import Article, BlogCategory
from apps.blog.models.Article import COVER_CROP_SLOTS
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
        request = self.context.get("request")
        user = getattr(request, "user", None)
        moderator_profile = getattr(user, "moderator_profile", None) if user else None
        return bool(moderator_profile and obj.moderator_profile_id == moderator_profile.id)


class ArticleDetailSerializer(ArticleListSerializer):
    class Meta(ArticleListSerializer.Meta):
        fields = ArticleListSerializer.Meta.fields + ["body_html", "moderator_comment"]


class ArticleCreateUpdateSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=BlogCategory.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Article
        fields = [
            "title",
            "subtitle",
            "cover_image",
            "cover_crops",
            "body_html",
            "category",
        ]

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title is required.")
        return value

    def validate_body_html(self, value):
        return sanitize_html(value)

    def validate_cover_crops(self, value):
        # Arrives as a JSON-encoded string over multipart (cover_image rides
        # alongside it in the same request), or already-parsed on a plain
        # JSON request -- accept either.
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError("cover_crops must be valid JSON.") from exc

        if not isinstance(value, dict):
            raise serializers.ValidationError("cover_crops must be an object.")

        for slot in COVER_CROP_SLOTS:
            crop = value.get(slot)
            if not isinstance(crop, dict):
                raise serializers.ValidationError(f"cover_crops.{slot} is required.")
            x, y = crop.get("x"), crop.get("y")
            width, height = crop.get("width"), crop.get("height")
            if not isinstance(x, (int, float)) or not (0 <= x <= 100):
                raise serializers.ValidationError(f"cover_crops.{slot}.x must be between 0 and 100.")
            if not isinstance(y, (int, float)) or not (0 <= y <= 100):
                raise serializers.ValidationError(f"cover_crops.{slot}.y must be between 0 and 100.")
            if not isinstance(width, (int, float)) or not (0 < width <= 100):
                raise serializers.ValidationError(f"cover_crops.{slot}.width must be between 0 and 100.")
            if not isinstance(height, (int, float)) or not (0 < height <= 100):
                raise serializers.ValidationError(f"cover_crops.{slot}.height must be between 0 and 100.")

        return {slot: value[slot] for slot in COVER_CROP_SLOTS}
