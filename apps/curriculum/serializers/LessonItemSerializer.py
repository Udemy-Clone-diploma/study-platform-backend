from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.curriculum.models import LessonItem

from .TestSerializer import TestSerializer


class LessonItemSerializer(serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField()
    test = TestSerializer(read_only=True)

    class Meta:
        model = LessonItem
        fields = [
            "id",
            "item_type",
            "order",
            # TEXT
            "content",
            "body_html",
            # VIDEO
            "video_url",
            "original_video_name",
            "duration_minutes",
            # TEST
            "test",
            # META
            "created_at",
            "updated_at",
            "source_lesson_item_id",
        ]

    def get_video_url(self, obj) -> str | None:
        if obj.video_url:
            return obj.video_url
        return absolute_media_url(obj.video, self.context.get("request"))
