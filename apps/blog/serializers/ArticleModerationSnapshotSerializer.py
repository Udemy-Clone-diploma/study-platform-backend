from rest_framework import serializers

from apps.blog.models import ArticleModerationSnapshot
from apps.common.files import absolute_media_url


class ArticleModerationSnapshotSerializer(serializers.ModelSerializer):
    article_slug = serializers.CharField(source="article.slug", read_only=True)
    article_status = serializers.CharField(source="article.status", read_only=True)
    cover_image = serializers.SerializerMethodField()
    moderator_name = serializers.SerializerMethodField()

    class Meta:
        model = ArticleModerationSnapshot
        fields = [
            "id",
            "article_id",
            "article_slug",
            "article_status",
            "decision",
            "comment",
            "title",
            "subtitle",
            "cover_image",
            "cover_crops",
            "author_name",
            "moderator_name",
            "created_at",
        ]

    def get_cover_image(self, obj) -> str | None:
        return absolute_media_url(obj.cover_image, self.context.get("request"))

    def get_moderator_name(self, obj) -> str | None:
        return obj.moderator_profile.user.get_full_name() if obj.moderator_profile else None
