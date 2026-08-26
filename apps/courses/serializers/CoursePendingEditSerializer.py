from rest_framework import serializers

from apps.courses.models import CoursePendingEdit


class CoursePendingEditReadSerializer(serializers.ModelSerializer):
    draft_course_slug = serializers.CharField(source="draft_course.slug", read_only=True)
    changed_fields = serializers.SerializerMethodField()

    class Meta:
        model = CoursePendingEdit
        fields = [
            "status",
            "draft_course_slug",
            "moderator_comment",
            "changed_fields",
            "submitted_at",
            "created_at",
            "updated_at",
        ]

    def get_changed_fields(self, obj) -> list[str]:
        from apps.courses.services.pending_edit_service import compute_pending_edit_changed_fields

        return compute_pending_edit_changed_fields(obj)
