from rest_framework import serializers


class _AttemptAnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    selected_indices = serializers.ListField(
        child=serializers.IntegerField(), required=False,
    )
    answer_bool = serializers.BooleanField(required=False, allow_null=True)
    answer_text = serializers.CharField(required=False, allow_blank=True)


class AttemptSubmitSerializer(serializers.Serializer):
    answers = _AttemptAnswerSerializer(many=True)
