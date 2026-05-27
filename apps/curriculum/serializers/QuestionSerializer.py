from rest_framework import serializers

from apps.curriculum.models import Question


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "id", "question_type", "text",
            "options", "correct_index", "correct_bool", "sample_answer",
            "order",
        ]
