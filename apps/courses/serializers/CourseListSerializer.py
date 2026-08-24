from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.courses.models import Course

from .CategorySerializer import CategorySerializer
from .TagSerializer import TagSerializer


class CourseListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    teacher_name = serializers.CharField(
        source="teacher_profile.user.get_full_name",
        read_only=True,
    )
    image = serializers.SerializerMethodField()
    price = serializers.DecimalField(
        source="min_price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    original_price = serializers.SerializerMethodField()
    currency = serializers.CharField(source="min_currency", read_only=True, allow_null=True)
    enrolled_at = serializers.DateTimeField(read_only=True, default=None)
    enrollment_access_status = serializers.CharField(read_only=True, default=None, allow_null=True)
    students_enrolled_last_30_days = serializers.IntegerField(read_only=True, default=0)

    pending_edit_status = serializers.SerializerMethodField()
    moderator_id = serializers.IntegerField(
        source="moderator_profile_id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Course
        fields = [
            "id",
            "image",
            "title",
            "subtitle",
            "short_description",
            "slug",
            "teacher_name",
            "category",
            "level",
            "language",
            "mode",
            "delivery_type",
            "course_type",
            "price",
            "original_price",
            "currency",
            "duration_hours",
            "lessons_count",
            "with_certificate",
            "is_on_sale",
            "discount_percent",
            "rating_avg",
            "rating_count",
            "students_count",
            "students_enrolled_last_30_days",
            "status",
            "published_at",
            "created_at",
            "tags",
            "enrolled_at",
            "enrollment_access_status",
            "pending_edit_status",
            "moderator_id",
        ]

    def get_image(self, obj) -> str | None:
        return absolute_media_url(obj.image, self.context.get("request"))

    def get_original_price(self, obj) -> str | None:
        original = getattr(obj, "original_min_price", None)
        if original is None or original == obj.min_price:
            return None
        return f"{original:.2f}"

    def get_pending_edit_status(self, obj) -> str | None:
        try:
            return obj.pending_edit.status
        except Exception:
            return None
