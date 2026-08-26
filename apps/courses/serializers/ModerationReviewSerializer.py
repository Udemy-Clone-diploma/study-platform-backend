from rest_framework import serializers

from apps.courses.models import ModerationReview


class ModerationReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModerationReview
        fields = [
            "basics_field_statuses",
            "basics_action",
            "basics_comment",
            "content_item_statuses",
            "content_action",
            "content_comment",
            "final_action",
            "final_comment",
            "updated_at",
        ]
