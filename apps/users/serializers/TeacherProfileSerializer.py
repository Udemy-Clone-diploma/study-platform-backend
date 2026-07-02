from rest_framework import serializers

from apps.users.models import TeacherProfile


class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = [
            "id", "bio", "experience", "specialization", "rating",
            "years_experience", "partnerships_count",
        ]
        read_only_fields = ["rating"]
