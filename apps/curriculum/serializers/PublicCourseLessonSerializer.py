from rest_framework import serializers

from apps.curriculum.models import Lesson


class PublicCourseLessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = [
            "id",
            "title",
            "order",
            "duration_minutes",
            "is_preview",
            "unlock_after_days",
            "requires_previous",
            "is_mandatory",
        ]
        read_only_fields = fields
