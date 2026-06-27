from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.curriculum.models import Test
from apps.curriculum.services import TestAttemptService

from .QuestionSerializer import QuestionSerializer
from .QuestionStudentSerializer import QuestionStudentSerializer


class TestSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            "id", "title", "description", "passing_score",
            "duration_minutes", "allow_retakes", "max_attempts",
            "order", "questions",
        ]

    @extend_schema_field(QuestionSerializer(many=True))
    def get_questions(self, obj):
        # Students must never receive the answer key before submitting.
        if self.context.get("hide_answers"):
            return QuestionStudentSerializer(obj.questions.all(), many=True).data
        return QuestionSerializer(obj.questions.all(), many=True).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Enrich with this student's attempt status so the player needs no extra call.
        student_profile = self.context.get("student_profile")
        if student_profile is not None:
            attempts_used = TestAttemptService.attempts_used(student_profile, instance)
            last = TestAttemptService.last_attempt(student_profile, instance)
            data["attempts_used"] = attempts_used
            data["can_attempt"] = TestAttemptService.can_attempt(instance, attempts_used)
            data["last_attempt"] = (
                {
                    "id": last.id,
                    "attempt_number": last.attempt_number,
                    "score": last.score,
                    "passed": last.passed,
                    "submitted_at": last.submitted_at,
                }
                if last is not None
                else None
            )
        return data
