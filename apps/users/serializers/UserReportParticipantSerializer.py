from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.users.models import User


class UserReportParticipantSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="get_full_name", read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "name",
            "email",
            "date_joined",
            "role",
            "status",
            "avatar",
            "is_blocked",
        ]
        read_only_fields = fields

    def get_avatar(self, obj: User) -> str | None:
        return absolute_media_url(obj.avatar, self.context.get("request"))
