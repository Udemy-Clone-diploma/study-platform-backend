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

    test_average = serializers.FloatField(allow_null=True)
    tests_passed = serializers.IntegerField()
    tests_failed = serializers.IntegerField()
    tests_skipped = serializers.IntegerField()
    tests_total = serializers.IntegerField()

    is_with_teacher = serializers.BooleanField()

    homework_average = serializers.FloatField(allow_null=True)
    homework_graded = serializers.IntegerField()
    homework_ungraded = serializers.IntegerField()
    homework_total = serializers.IntegerField()

    can_complete_course = serializers.BooleanField()
    is_course_completed = serializers.BooleanField()
