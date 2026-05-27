from rest_framework import serializers

from apps.courses.models import Question


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "id", "question_type", "text",
            "options", "correct_index", "correct_bool", "sample_answer",
            "order",
        ]
