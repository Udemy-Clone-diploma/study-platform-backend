from rest_framework import serializers

from apps.curriculum.models import Question


class QuestionCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = [
            "question_type", "text", "options",
            "correct_indices", "correct_bool", "sample_answer", "accepted_answers",
        ]
        extra_kwargs = {
            "question_type": {"required": False},
            "options": {"required": False},
            "correct_indices": {"required": False},
            "correct_bool": {"required": False},
            "sample_answer": {"required": False},
            "accepted_answers": {"required": False},
        }
