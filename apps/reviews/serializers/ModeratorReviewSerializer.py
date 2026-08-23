from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.reviews.models import Review

from .ReviewSerializer import ReviewStudentSerializer
from .TopReviewSerializer import ReviewCourseSerializer


class ModeratorReviewSerializer(serializers.ModelSerializer):
    """Review with its report/moderation detail, for the moderator "flagged reviews" queue."""

    student = ReviewStudentSerializer(read_only=True)
    course = ReviewCourseSerializer(read_only=True)
    report_count = serializers.IntegerField(read_only=True)
    reports = serializers.SerializerMethodField()
    moderator_id = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id", "student", "course", "rating", "text", "created_at",
            "report_count", "reports", "moderation_status", "moderator_id",
        ]

    def get_moderator_id(self, obj) -> int | None:
        return obj.moderator_profile_id

    def get_reports(self, obj) -> list[dict]:
        request = self.context.get("request")
        return [
            {
                "reporter_id": r.reporter_id,
                "reporter_name": r.reporter.get_full_name(),
                "reporter_avatar": absolute_media_url(r.reporter.avatar, request),
                "reason": r.reason,
                "created_at": r.created_at,
            }
            for r in obj.reports.all()
        ]
