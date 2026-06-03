from rest_framework import serializers

from apps.curriculum.models import Test

from .QuestionSerializer import QuestionSerializer


class TestSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Test
        fields = ["id", "title", "description", "passing_score", "order", "questions"]
