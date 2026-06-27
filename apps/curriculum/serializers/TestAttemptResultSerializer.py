from rest_framework import serializers


class _QuestionResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    question_type = serializers.CharField()
    text = serializers.CharField()
    options = serializers.ListField(child=serializers.CharField())
    order = serializers.IntegerField()
    is_correct = serializers.BooleanField()
    # echoed submission + revealed answer key (shape depends on question_type)
    selected_indices = serializers.ListField(child=serializers.IntegerField(), required=False)
    correct_indices = serializers.ListField(child=serializers.IntegerField(), required=False)
    answer_bool = serializers.BooleanField(required=False, allow_null=True)
    correct_bool = serializers.BooleanField(required=False, allow_null=True)
    answer_text = serializers.CharField(required=False, allow_blank=True)
    sample_answer = serializers.CharField(required=False, allow_blank=True)
    accepted_answers = serializers.ListField(child=serializers.CharField(), required=False)


class TestAttemptResultSerializer(serializers.Serializer):
    """Schema for the submit-and-grade response (built as a dict by the service)."""

    attempt_id = serializers.IntegerField()
    attempt_number = serializers.IntegerField()
    score = serializers.IntegerField()
    correct_count = serializers.IntegerField()
    total_count = serializers.IntegerField()
    passed = serializers.BooleanField()
    passing_score = serializers.IntegerField()
    can_retake = serializers.BooleanField()
    attempts_used = serializers.IntegerField()
    max_attempts = serializers.IntegerField(allow_null=True)
    questions = _QuestionResultSerializer(many=True)
