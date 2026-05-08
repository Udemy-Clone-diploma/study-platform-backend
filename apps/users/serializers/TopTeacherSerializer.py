from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.users.models import TeacherProfile


class TopTeacherSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.get_full_name", read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = TeacherProfile
        fields = [
            "id",
            "name",
            "avatar",
            "specialization",
            "experience",
            "rating",
        ]

    def get_avatar(self, obj: TeacherProfile) -> str | None:
        return absolute_media_url(obj.user.avatar, self.context.get("request"))
