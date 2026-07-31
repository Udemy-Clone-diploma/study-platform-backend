from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.courses.models import Course

from .PublicCategorySerializer import PublicCategorySerializer
from .PublicTagSerializer import PublicTagSerializer


class PublicCourseListSerializer(serializers.ModelSerializer):
    category = PublicCategorySerializer(read_only=True)
    tags = PublicTagSerializer(many=True, read_only=True)
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
    currency = serializers.CharField(
        source="min_currency",
        read_only=True,
        allow_null=True,
    )
    students_enrolled_last_30_days = serializers.IntegerField(
        read_only=True,
        default=0,
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
            "currency",
            "duration_hours",
            "lessons_count",
            "with_certificate",
            "is_on_sale",
            "rating_avg",
            "rating_count",
            "students_count",
            "students_enrolled_last_30_days",
            "published_at",
            "created_at",
            "tags",
        ]
        read_only_fields = fields

    def get_image(self, obj: Course) -> str | None:
        return absolute_media_url(obj.image, self.context.get("request"))
