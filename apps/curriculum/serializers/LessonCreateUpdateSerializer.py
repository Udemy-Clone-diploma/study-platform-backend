from rest_framework import serializers

from apps.common.sanitize import sanitize_html
from apps.curriculum.models import Lesson


class LessonCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = [
            "title", "content_type", "content", "video", "video_url",
            "body_html", "meeting_url", "duration_minutes", "min_score", "is_preview",
        ]
        extra_kwargs = {
            "content": {"required": False},
            "video": {"required": False},
            "video_url": {"required": False},
            "body_html": {"required": False},
            "meeting_url": {"required": False},
            "duration_minutes": {"required": False},
            "min_score": {"required": False},
            "is_preview": {"required": False},
        }

    def validate_body_html(self, value):
        return sanitize_html(value)

    def save(self, **kwargs):
        video = self.validated_data.get("video")
        if video and hasattr(video, "name"):
            kwargs["original_video_name"] = video.name
        return super().save(**kwargs)