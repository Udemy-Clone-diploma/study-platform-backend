from rest_framework import serializers

from apps.curriculum.models import Lesson


class LessonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ["id", "title", "order", "duration_minutes", "is_preview"]


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
