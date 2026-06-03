from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.courses.models import Category, CoursePendingEdit


class CoursePendingEditReadSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    category_id = serializers.IntegerField(allow_null=True, read_only=True)

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
            "submitted_at", "created_at", "updated_at",
        ]

    def get_image(self, obj) -> str | None:
        return absolute_media_url(obj.image, self.context.get("request"))


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
