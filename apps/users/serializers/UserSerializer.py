from rest_framework import serializers

from apps.users.models import User

from .ModeratorProfileSerializer import ModeratorProfileSerializer
from .StudentProfileSerializer import StudentProfileSerializer
from .TeacherProfileSerializer import TeacherProfileSerializer

PROFILE_SERIALIZERS = {
    "student": StudentProfileSerializer,
    "teacher": TeacherProfileSerializer,
    "moderator": ModeratorProfileSerializer,
}


class UserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "status",
            "avatar",
            "language",
            "is_blocked",
            "date_joined",
            "profile",
        ]
        read_only_fields = ["id", "date_joined"]

    def get_profile(self, obj):
        serializer_class = PROFILE_SERIALIZERS.get(obj.role)
        if not serializer_class:
            return None
        profile_attr = f"{obj.role}_profile"
        if not hasattr(obj, profile_attr):
            return None
        return serializer_class(getattr(obj, profile_attr)).data
