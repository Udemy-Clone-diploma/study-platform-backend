from rest_framework import serializers

from apps.courses.models import Course

from .CategorySerializer import CategorySerializer
from .CourseTeacherSerializer import CourseTeacherSerializer
from .TagSerializer import TagSerializer


class CourseDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    teacher = CourseTeacherSerializer(source="teacher_profile", read_only=True)
    moderator_id = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "title", "short_description", "full_description", "slug",
            "teacher", "moderator_id", "category", "level", "language", "mode",
            "delivery_type", "course_type", "pricing_type", "price", "installment_count",
            "installment_amount", "duration_hours", "lessons_count",
            "with_certificate", "is_on_sale", "rating_avg", "students_count", "status",
            "created_at", "updated_at", "published_at", "tags",
        ]

    def get_moderator_id(self, obj):
        return obj.moderator_profile.id if obj.moderator_profile else None
