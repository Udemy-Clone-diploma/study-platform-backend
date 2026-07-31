from rest_framework import serializers

from .PublicCourseListSerializer import PublicCourseListSerializer


class EnrolledCourseListSerializer(PublicCourseListSerializer):
    enrolled_at = serializers.DateTimeField(read_only=True, default=None)
    progress_percent = serializers.SerializerMethodField()

    class Meta(PublicCourseListSerializer.Meta):
        fields = PublicCourseListSerializer.Meta.fields + [
            "enrolled_at",
            "progress_percent",
        ]
        read_only_fields = fields

    def get_progress_percent(self, obj) -> int:
        completed = getattr(obj, "enrollment_lessons_completed", None) or 0
        total = obj.lessons_count or 0
        if total <= 0:
            return 0
        return (completed * 100) // total
