from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.courses.models import Course
from apps.curriculum.serializers.PublicCourseModuleSerializer import (
    PublicCourseModuleSerializer,
)

from .PublicCategorySerializer import PublicCategorySerializer
from .PublicCourseCohortSerializer import PublicCourseCohortSerializer
from .PublicCourseDeliveryFormatSerializer import (
    PublicCourseDeliveryFormatSerializer,
)
from .PublicCourseTeacherSerializer import PublicCourseTeacherSerializer
from .PublicTagSerializer import PublicTagSerializer


class PublicCourseDetailSerializer(serializers.ModelSerializer):
    category = PublicCategorySerializer(read_only=True)
    tags = PublicTagSerializer(many=True, read_only=True)
    teacher = PublicCourseTeacherSerializer(
        source="teacher_profile",
        read_only=True,
    )
    modules = PublicCourseModuleSerializer(many=True, read_only=True)
    delivery_formats = PublicCourseDeliveryFormatSerializer(
        many=True,
        read_only=True,
    )
    cohorts = PublicCourseCohortSerializer(many=True, read_only=True)
    image = serializers.SerializerMethodField()
    total_duration_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "image",
            "title",
            "subtitle",
            "short_description",
            "full_description",
            "slug",
            "teacher",
            "category",
            "level",
            "language",
            "mode",
            "delivery_type",
            "course_type",
            "duration_hours",
            "lessons_count",
            "total_duration_minutes",
            "with_certificate",
            "certificate_description",
            "is_on_sale",
            "passing_score",
            "rating_avg",
            "rating_count",
            "students_count",
            "created_at",
            "updated_at",
            "published_at",
            "tags",
            "modules",
            "delivery_formats",
            "cohorts",
        ]
        read_only_fields = fields

    def get_image(self, obj: Course) -> str | None:
        return absolute_media_url(obj.image, self.context.get("request"))

    def get_total_duration_minutes(self, obj: Course) -> int:
        return sum(
            lesson.duration_minutes or 0
            for module in obj.modules.all()
            for lesson in module.lessons.all()
        )
