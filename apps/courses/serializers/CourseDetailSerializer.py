from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.courses.models import Course
from apps.curriculum.serializers import ModuleSerializer
from apps.users.permissions import IsAdminOrModerator

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
    image_hash = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()
    group_chat_url = serializers.SerializerMethodField()
    total_duration_minutes = serializers.SerializerMethodField()
    moderation_review = ModerationReviewSerializer(read_only=True)

    class Meta:
        model = Course
        fields = [
            "id", "image", "image_hash", "title", "subtitle", "short_description", "full_description",
            "slug", "teacher", "moderator_id", "category",
            "level", "language", "mode", "delivery_type", "course_type",
            "duration_hours", "lessons_count", "total_duration_minutes",
            "with_certificate", "certificate_description", "is_on_sale", "discount_percent",
            "passing_score",
            "rating_avg", "rating_count", "students_count", "status",
            "moderator_comment",
            "created_at", "updated_at", "published_at",
            "is_enrolled", "group_chat_url",
            "tags", "modules", "delivery_formats", "cohorts",
            "moderation_review",
        ]

    def get_moderator_id(self, obj) -> int | None:
        return obj.moderator_profile.id if obj.moderator_profile else None

    def get_image(self, obj) -> str | None:
        return absolute_media_url(obj.image, self.context.get("request"))

    def get_image_hash(self, obj) -> str | None:
        # Only the moderator review diff needs this -- gate it on role. The
        # value is a cheap cached field (computed on save), not read here.
        request = self.context.get("request")
        if not request or not IsAdminOrModerator().has_permission(request, None):
            return None
        return obj.image_hash or None

    def get_group_chat_url(self, obj) -> str | None:
        return None

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
