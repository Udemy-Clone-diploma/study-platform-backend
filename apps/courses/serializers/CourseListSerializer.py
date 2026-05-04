from rest_framework import serializers

from apps.courses.models import Course

from .CategorySerializer import CategorySerializer
from .TagSerializer import TagSerializer


class CourseListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "title", "short_description", "slug", "teacher_name", "category",
            "level", "language", "mode", "delivery_type", "course_type", "pricing_type",
            "price", "duration_hours", "lessons_count", "with_certificate", "is_on_sale",
            "rating_avg", "students_count", "status", "published_at", "tags",
        ]

    def get_teacher_name(self, obj):
        user = obj.teacher_profile.user
        return f"{user.first_name} {user.last_name}".strip()
