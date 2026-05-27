from rest_framework import serializers

from apps.courses.models import Question


class QuestionCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "question_type", "text",
            "options", "correct_index", "correct_bool", "sample_answer",
        ]
        extra_kwargs = {
            "question_type": {"required": False},
            "options": {"required": False},
            "correct_index": {"required": False},
            "correct_bool": {"required": False},
            "sample_answer": {"required": False},
        }
