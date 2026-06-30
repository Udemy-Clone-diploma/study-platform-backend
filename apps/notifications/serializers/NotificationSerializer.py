from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.notifications.models import Notification


class NotificationActorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source="get_full_name")
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, obj) -> str | None:
        return absolute_media_url(obj.avatar, self.context.get("request"))


class NotificationSerializer(serializers.ModelSerializer):
    actor = NotificationActorSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "title",
            "body",
            "link_url",
            "actor",
            "payload",
            "is_read",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "type",
            "title",
            "body",
            "link_url",
            "actor",
            "payload",
            "created_at",
        ]
