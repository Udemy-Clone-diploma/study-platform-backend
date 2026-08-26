from rest_framework import serializers

from apps.curriculum.models import Lesson


class LessonCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = [
            "title",
            "duration_minutes",
            "min_score",
            "is_preview",
            "meeting_url",
            "unlock_after_days",
            "requires_previous",
            "is_manually_locked",
            "is_mandatory",
        ]
        extra_kwargs = {
            "duration_minutes": {"required": False},
            "min_score": {"required": False},
            "is_preview": {"required": False},
            "meeting_url": {"required": False},
            "unlock_after_days": {"required": False},
            "requires_previous": {"required": False},
            "is_manually_locked": {"required": False},
            "is_mandatory": {"required": False},
        }
