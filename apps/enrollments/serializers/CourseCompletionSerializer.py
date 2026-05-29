from rest_framework import serializers

from apps.enrollments.models import CourseCompletion


class CourseCompletionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseCompletion
        fields = [
            "id", "course", "title", "teacher_name", "level", "image_url",
            "progress_percent", "started_at", "completed_at", "final_score", "certificate_url",
        ]
        read_only_fields = fields
