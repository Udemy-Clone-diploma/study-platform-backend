from rest_framework import serializers

from apps.curriculum.models import Lesson


class LessonCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ["title", "duration_minutes", "min_score", "is_preview", "meeting_url"]
        extra_kwargs = {
            "duration_minutes": {"required": False},
            "min_score": {"required": False},
            "is_preview": {"required": False},
            "meeting_url": {"required": False},
        }
