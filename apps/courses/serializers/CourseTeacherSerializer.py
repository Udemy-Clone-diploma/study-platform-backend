from rest_framework import serializers

from apps.users.models import TeacherProfile


class CourseTeacherSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.get_full_name", read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = TeacherProfile
        fields = ["id", "name", "avatar", "bio"]

    def get_avatar(self, obj: TeacherProfile) -> str | None:
        avatar = obj.user.avatar
        if not avatar:
            return None
        request = self.context.get("request")
        url = avatar.url
        return request.build_absolute_uri(url) if request else url
