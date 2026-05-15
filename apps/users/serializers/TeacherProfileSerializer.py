from rest_framework import serializers

from apps.users.models import TeacherProfile


class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = ["id", "bio", "experience", "specialization", "rating"]
        read_only_fields = ["rating"]
