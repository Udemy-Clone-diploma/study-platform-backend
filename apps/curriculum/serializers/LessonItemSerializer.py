from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.curriculum.models import LessonItem
from apps.users.permissions import IsAdminOrModerator

from .TestSerializer import TestSerializer


class LessonItemSerializer(serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField()
    video_hash = serializers.SerializerMethodField()
    test = TestSerializer(read_only=True)

    class Meta:
        model = LessonItem
        fields = [
            "id",
            "item_type",
            "order",
            # TEXT
            "body_html",
            # VIDEO
            "video_url",
            "video_hash",
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

    def get_video_hash(self, obj) -> str | None:
        """Cached content hash of the uploaded video file, if any (None for an
        external video_url link). Cloning duplicates the file under a fresh
        generated path (see duplicate_file_field), so comparing video_url alone
        always reports a change for uploaded videos even when the content is
        identical, compare this instead when a file is actually attached.

        Only the moderator review diff needs this, gate it on role so a
        regular course-detail fetch doesn't pay to serialize it (the value
        itself is a cheap cached field, computed on save, not read here).
        """
        request = self.context.get("request")
        if not request or not IsAdminOrModerator().has_permission(request, None):
            return None
        return obj.video_hash or None
