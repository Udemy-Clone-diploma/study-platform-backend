from rest_framework import serializers

from apps.curriculum.models import Lesson

from .LessonDocumentSerializer import LessonDocumentSerializer
from .LessonItemSerializer import LessonItemSerializer


class LessonSerializer(serializers.ModelSerializer):
    documents = LessonDocumentSerializer(many=True, read_only=True)
    items = LessonItemSerializer(many=True, read_only=True)
    meeting_url = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            "id", "title", "order", "duration_minutes", "is_preview",
            "min_score", "meeting_url", "unlock_after_days", "requires_previous",
            "is_manually_locked", "documents", "items", "source_lesson_id",
        ]

    def get_meeting_url(self, obj) -> str | None:
        if not self.context.get("has_enrollment_access"):
            return None
        return obj.meeting_url or None
