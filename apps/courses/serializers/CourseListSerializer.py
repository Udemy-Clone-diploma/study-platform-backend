from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.courses.models import Course

from .CategorySerializer import CategorySerializer
from .TagSerializer import TagSerializer


class CourseListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    teacher_name = serializers.CharField(
        source="teacher_profile.user.get_full_name", read_only=True,
    )
    image = serializers.SerializerMethodField()
    price = serializers.DecimalField(
        source="min_price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    currency = serializers.CharField(source="min_currency", read_only=True, allow_null=True)
    enrolled_at = serializers.DateTimeField(read_only=True, default=None)

    pending_edit_status = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "image", "title", "subtitle", "short_description", "slug",
            "teacher_name", "category",
            "level", "language", "mode", "delivery_type", "course_type",
            "price", "currency", "duration_hours", "lessons_count",
            "with_certificate", "is_on_sale",
            "rating_avg", "rating_count", "students_count", "status",
            "published_at", "created_at", "tags", "enrolled_at",
            "pending_edit_status",
        ]

    def get_image(self, obj) -> str | None:
        return absolute_media_url(obj.image, self.context.get("request"))

    def get_pending_edit_status(self, obj) -> str | None:
        try:
            return obj.pending_edit.status
        except Exception:
            return None
