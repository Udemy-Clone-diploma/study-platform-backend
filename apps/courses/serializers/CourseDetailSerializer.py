from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.courses.models import Course
from apps.curriculum.serializers import ModuleSerializer

from .CategorySerializer import CategorySerializer
from .CohortSerializer import CohortSerializer
from .CourseDeliveryFormatSerializer import CourseDeliveryFormatSerializer
from .CourseTeacherSerializer import CourseTeacherSerializer
from .ModerationReviewSerializer import ModerationReviewSerializer
from .TagSerializer import TagSerializer


class CourseDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    teacher = CourseTeacherSerializer(source="teacher_profile", read_only=True)
    moderator_id = serializers.SerializerMethodField()
    modules = ModuleSerializer(many=True, read_only=True)
    delivery_formats = CourseDeliveryFormatSerializer(many=True, read_only=True)
    cohorts = CohortSerializer(many=True, read_only=True)
    image = serializers.SerializerMethodField()
    total_duration_minutes = serializers.SerializerMethodField()
    moderation_review = ModerationReviewSerializer(read_only=True)
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "image", "title", "subtitle", "short_description", "full_description",
            "slug", "teacher", "moderator_id", "category",
            "level", "language", "mode", "delivery_type", "course_type",
            "duration_hours", "lessons_count", "total_duration_minutes",
            "with_certificate", "is_on_sale",
            "rating_avg", "rating_count", "students_count", "status",
            "moderator_comment",
            "created_at", "updated_at", "published_at",
            "tags", "modules", "delivery_formats", "cohorts",
            "moderation_review",
            "is_enrolled",
        ]

    def get_moderator_id(self, obj) -> int | None:
        return obj.moderator_profile.id if obj.moderator_profile else None

    def get_image(self, obj) -> str | None:
        return absolute_media_url(obj.image, self.context.get("request"))

    def get_total_duration_minutes(self, obj) -> int:
        return sum(
            lesson.duration_minutes or 0
            for module in obj.modules.all()
            for lesson in module.lessons.all()
        )

    def get_is_enrolled(self, obj) -> bool:
        from apps.enrollments.services.enrollment_service import EnrollmentService
        request = self.context.get("request")
        if request is None:
            return False
        return EnrollmentService.is_enrolled(request.user, obj)
