from rest_framework import serializers

from apps.users.models import StudentProfile


class PublicStudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = ["learning_goals", "education_level"]
        read_only_fields = fields
