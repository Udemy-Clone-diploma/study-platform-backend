from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.users.models import User


class PublicChatUserSerializer(serializers.ModelSerializer):
    """Minimal user data safe to expose to regular chat participants."""

    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "first_name", "last_name", "role", "avatar"]
        read_only_fields = fields

    def get_name(self, obj: User) -> str:
        return obj.get_full_name() or "User"

    def get_avatar(self, obj: User) -> str | None:
        return absolute_media_url(obj.avatar, self.context.get("request"))


class ModerationChatUserSerializer(PublicChatUserSerializer):
    """Chat user data available only from moderation endpoints."""

    class Meta(PublicChatUserSerializer.Meta):
        fields = [*PublicChatUserSerializer.Meta.fields, "email"]
