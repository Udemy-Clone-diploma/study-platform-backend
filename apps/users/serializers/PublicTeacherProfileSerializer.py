from rest_framework import serializers

from apps.users.models import TeacherProfile


class PublicTeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = [
            "bio",
            "experience",
            "specialization",
            "rating",
            "years_experience",
            "partnerships_count",
        ]
        read_only_fields = fields
