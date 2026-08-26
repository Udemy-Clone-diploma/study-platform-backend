from rest_framework import serializers

from apps.courses.models import Category
from apps.users.models import TeacherApplication


class TeacherApplicationCreateSerializer(serializers.ModelSerializer):
    directions = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = TeacherApplication
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "date_of_birth",
            "phone_number",
            "bio",
            "experience",
            "specialization",
            "years_experience",
            "directions",
            "motivation",
            "instagram",
            "linkedin",
            "behance",
        ]

    def validate_email(self, value):
        # Local import: apps.users.services.user_service imports back from
        # apps.users.serializers, so a module-level import here would cycle.
        from apps.users.services.teacher_application_service import TeacherApplicationService

        conflict = TeacherApplicationService.email_conflict(value)
        if conflict:
            raise serializers.ValidationError(conflict)
        return value
