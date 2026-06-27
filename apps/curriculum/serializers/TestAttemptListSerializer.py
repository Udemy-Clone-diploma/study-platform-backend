from rest_framework import serializers

from apps.curriculum.models import TestAttempt


class TestAttemptListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestAttempt
        fields = ["id", "attempt_number", "score", "passed", "submitted_at"]
