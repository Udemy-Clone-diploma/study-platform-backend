from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.courses.models import Category, CoursePendingEdit


class CoursePendingEditReadSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    category_id = serializers.IntegerField(allow_null=True, read_only=True)
    changed_fields = serializers.SerializerMethodField()

    class Meta:
        model = CoursePendingEdit
        fields = [
            "status",
            "title", "subtitle", "short_description", "full_description", "image",
            "level", "language", "mode", "delivery_type", "course_type",
            "duration_hours", "with_certificate", "is_on_sale",
            "category_id", "tag_ids",
            "modules_snapshot",
            "moderator_comment",
            "changed_fields",
            "submitted_at", "created_at", "updated_at",
        ]

    def get_image(self, obj) -> str | None:
        return absolute_media_url(obj.image, self.context.get("request"))

    def get_changed_fields(self, obj) -> list[str]:
        from apps.courses.services.pending_edit_service import compute_pending_edit_changed_fields
        return compute_pending_edit_changed_fields(obj)


class CoursePendingEditWriteSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = CoursePendingEdit
        fields = [
            "title", "subtitle", "short_description", "full_description", "image",
            "level", "language", "mode", "delivery_type", "course_type",
            "duration_hours", "with_certificate", "is_on_sale",
            "category_id", "tag_ids",
            "modules_snapshot",
        ]
