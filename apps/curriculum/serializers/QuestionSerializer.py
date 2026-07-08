from rest_framework import serializers

from apps.curriculum.models import Question


class QuestionSerializer(serializers.ModelSerializer):
    """Full question, including answers. Teacher / owner authoring + review only."""

    class Meta:
        model = Question
        fields = [
            "id", "question_type", "text", "options",
            "correct_indices", "correct_bool", "sample_answer", "accepted_answers",
            "order", "source_question_id",
        ]
