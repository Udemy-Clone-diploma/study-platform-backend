from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.curriculum.models import LessonDocument


class LessonDocumentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = LessonDocument
        fields = ["id", "original_name", "url", "created_at"]

    def get_url(self, obj) -> str | None:
        return absolute_media_url(obj.file, self.context.get("request"))
