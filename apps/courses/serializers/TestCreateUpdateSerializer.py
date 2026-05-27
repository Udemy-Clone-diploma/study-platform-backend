from rest_framework import serializers

from apps.courses.models import Test


class TestCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Test
        fields = ["title", "description", "passing_score"]
        extra_kwargs = {
            "description": {"required": False},
            "passing_score": {"required": False},
        }
