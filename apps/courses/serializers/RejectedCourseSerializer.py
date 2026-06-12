from .CourseListSerializer import CourseListSerializer
from .ModerationReviewSerializer import ModerationReviewSerializer


class RejectedCourseSerializer(CourseListSerializer):
    """CourseListSerializer extended with moderation_review and moderator_comment."""

    moderation_review = ModerationReviewSerializer(read_only=True)

    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + ["moderator_comment", "moderation_review"]
