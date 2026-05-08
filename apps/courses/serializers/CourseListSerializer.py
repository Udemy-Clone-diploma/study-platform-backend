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

    class Meta:
        model = Course
        fields = [
            "id", "image", "title", "short_description", "slug", "teacher_name", "category",
            "level", "language", "mode", "delivery_type", "course_type", "pricing_type",
            "price", "duration_hours", "lessons_count", "with_certificate", "is_on_sale",
            "rating_avg", "students_count", "status", "published_at", "tags",
        ]

    def get_image(self, obj):
        return absolute_media_url(obj.image, self.context.get("request"))
