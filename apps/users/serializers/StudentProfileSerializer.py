from rest_framework import serializers

from apps.users.models import StudentProfile


class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = ["date_of_birth", "learning_goals", "education_level"]
