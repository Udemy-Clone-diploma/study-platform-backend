from rest_framework import serializers

from apps.curriculum.models import Test


class TestCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Test
        fields = [
            "title", "description", "passing_score",
            "duration_minutes", "allow_retakes", "max_attempts",
        ]
        extra_kwargs = {
            "description": {"required": False},
            "passing_score": {"required": False},
            "duration_minutes": {"required": False},
            "allow_retakes": {"required": False},
            "max_attempts": {"required": False},
        }
