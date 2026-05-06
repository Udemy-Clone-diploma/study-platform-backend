from rest_framework import serializers

from apps.users.models import TeacherProfile


class TopTeacherSerializer(serializers.ModelSerializer):
    teacher_id = serializers.IntegerField(source="id", read_only=True)
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, obj):
        if not obj.user.avatar:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.user.avatar.url)
        return obj.user.avatar.url

    class Meta:
        model = TeacherProfile
        fields = [
            "teacher_id",
            "name",
            "avatar",
            "specialization",
            "experience",
            "rating",
        ]

    def get_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()