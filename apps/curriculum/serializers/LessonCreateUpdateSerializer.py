from rest_framework import serializers

from apps.curriculum.models import Lesson


class LessonCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = [
            "title", "content_type", "content", "video", "video_url",
            "body_html", "duration_minutes", "min_score", "is_preview",
        ]
        extra_kwargs = {
            "content": {"required": False},
            "video": {"required": False},
            "video_url": {"required": False},
            "body_html": {"required": False},
            "duration_minutes": {"required": False},
            "min_score": {"required": False},
            "is_preview": {"required": False},
        }
