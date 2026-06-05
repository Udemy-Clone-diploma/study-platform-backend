from rest_framework import serializers


class LessonCompletionResultSerializer(serializers.Serializer):
    lesson_id = serializers.IntegerField()
    completed_at = serializers.DateTimeField(allow_null=True)
    lessons_completed_count = serializers.IntegerField()


class CourseProgressSerializer(serializers.Serializer):
    enrollment_id = serializers.IntegerField()
    lessons_completed_count = serializers.IntegerField()
    lessons_count = serializers.IntegerField()
    completed_lesson_ids = serializers.ListField(child=serializers.IntegerField())
    last_lesson_id = serializers.IntegerField(allow_null=True)
    last_opened_at = serializers.DateTimeField(allow_null=True)
