from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.curriculum.models import Lesson
from .LessonDocumentSerializer import LessonDocumentSerializer


class LessonSerializer(serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField()
    documents = LessonDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = [
            "id", "title", "order", "duration_minutes", "is_preview",
            "content", "min_score", "video_url", "original_video_name", "documents",
        ]

    def get_video_url(self, obj) -> str | None:
        if obj.video_url:
            return obj.video_url
        return absolute_media_url(obj.video, self.context.get("request"))


class LessonDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = [
            "id",
            "title",
            "order",
            "duration_minutes",
            "is_preview",
            "content_type",
            "video_url",
            "body_html",
        ]