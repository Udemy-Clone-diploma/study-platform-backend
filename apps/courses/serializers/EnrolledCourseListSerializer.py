from rest_framework import serializers

from .CourseListSerializer import CourseListSerializer


class EnrolledCourseListSerializer(CourseListSerializer):
    progress_percent = serializers.SerializerMethodField()

    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + ["progress_percent"]

    def get_progress_percent(self, obj) -> int:
        completed = getattr(obj, "enrollment_lessons_completed", None) or 0
        total = obj.lessons_count or 0
        if total <= 0:
            return 0
        return (completed * 100) // total
