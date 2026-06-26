from rest_framework import serializers

from apps.curriculum.models import Question


class QuestionStudentSerializer(serializers.ModelSerializer):
    """Question as shown to a student before submitting: no answers revealed."""

    class Meta:
        model = Question
        fields = ["id", "question_type", "text", "options", "order"]
