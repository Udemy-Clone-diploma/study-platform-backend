from rest_framework import serializers

from apps.users.models import User, UserReport

from .PublicModeratorProfileSerializer import PublicModeratorProfileSerializer
from .PublicStudentProfileSerializer import PublicStudentProfileSerializer
from .PublicTeacherProfileSerializer import PublicTeacherProfileSerializer


PUBLIC_PROFILE_SERIALIZERS = {
    User.RoleChoices.STUDENT: PublicStudentProfileSerializer,
    User.RoleChoices.TEACHER: PublicTeacherProfileSerializer,
    User.RoleChoices.MODERATOR: PublicModeratorProfileSerializer,
}


class PublicUserSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()
    is_self = serializers.SerializerMethodField()
    has_reported = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "role",
            "avatar",
            "date_joined",
            "instagram",
            "linkedin",
            "facebook",
            "behance",
            "is_self",
            "has_reported",
            "profile",
        ]
        read_only_fields = fields

    def get_profile(self, obj: User) -> dict | None:
        serializer_class = PUBLIC_PROFILE_SERIALIZERS.get(obj.role)
        if serializer_class is None:
            return None

        profile_attr = f"{obj.role}_profile"
        if not hasattr(obj, profile_attr):
            return None

        return serializer_class(
            getattr(obj, profile_attr),
            context=self.context,
        ).data

    def get_is_self(self, obj: User) -> bool:
        request = self.context.get("request")
        return bool(
            request
            and request.user.is_authenticated
            and request.user.pk == obj.pk
        )

    def get_email(self, obj: User) -> str:
        request = self.context.get("request")
        viewer = getattr(request, "user", None)
        if (
            obj.role == User.RoleChoices.ADMINISTRATOR
            and getattr(viewer, "role", None) == User.RoleChoices.ADMINISTRATOR
        ):
            return obj.email
        return ""

    def get_has_reported(self, obj: User) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return UserReport.objects.filter(
            reported_user=obj,
            reporter=request.user,
            status__in=[
                UserReport.StatusChoices.PENDING,
                UserReport.StatusChoices.IN_REVIEW,
                UserReport.StatusChoices.ESCALATED,
            ],
        ).exists()

    def to_representation(self, instance: User) -> dict:
        data = super().to_representation(instance)
        request = self.context.get("request")
        viewer_role = getattr(getattr(request, "user", None), "role", None)
        if instance.role == User.RoleChoices.MODERATOR or (
            instance.role == User.RoleChoices.ADMINISTRATOR
            and viewer_role != User.RoleChoices.ADMINISTRATOR
        ):
            for field in ("instagram", "linkedin", "facebook", "behance"):
                data[field] = ""
        return data
