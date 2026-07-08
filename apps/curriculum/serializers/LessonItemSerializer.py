from rest_framework import serializers

from apps.common.files import absolute_media_url, file_content_hash
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
        """Content hash of the uploaded video file, if any (None for an external
        video_url link). Cloning duplicates the file under a fresh generated path
        (see duplicate_file_field), so comparing video_url alone always reports a
        change for uploaded videos even when the content is identical — compare
        this instead when a file is actually attached.

        Only the moderator review diff needs this, and hashing means reading the
        full video file -- gate it on role so every student/teacher course-detail
        fetch doesn't pay to re-hash every video on the course.
        """
        request = self.context.get("request")
        if not request or not IsAdminOrModerator().has_permission(request, None):
            return None
        return file_content_hash(obj.video)
