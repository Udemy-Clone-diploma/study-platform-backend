from rest_framework import serializers

from apps.courses.serializers import CategorySerializer
from apps.users.models import TeacherApplication


class TeacherApplicationSerializer(serializers.ModelSerializer):
    directions = CategorySerializer(many=True, read_only=True)
    moderator_name = serializers.CharField(
        source="moderator_profile.user.get_full_name", read_only=True, default=None,
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
            "status",
            "moderator_name",
            "moderator_comment",
            "submitted_at",
            "decided_at",
        ]
        read_only_fields = fields
