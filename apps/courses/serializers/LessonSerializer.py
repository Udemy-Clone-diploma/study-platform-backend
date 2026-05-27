from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.courses.models import Lesson


class LessonSerializer(serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ["id", "title", "content", "video_url", "order", "duration_minutes", "min_score"]

    def get_video_url(self, obj) -> str | None:
        return absolute_media_url(obj.video, self.context.get("request"))
