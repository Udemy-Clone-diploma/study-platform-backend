from rest_framework import serializers

from apps.common.sanitize import sanitize_html
from apps.courses.models import Category, Course, Tag
from apps.users.models import User

# Status transitions a course owner (teacher) may trigger directly via this
# serializer (i.e. via a plain PATCH). Anything else — becoming PUBLISHED,
# REJECTED, NEEDS_REVISION, or the internal-only PENDING_EDIT shadow-draft
# status — only happens through the moderation service methods
# (approve_course/reject_course/restore_rejected_course/clone_for_pending_edit),
# which set the field directly on the model and never go through this serializer.
_TEACHER_ALLOWED_STATUS_TRANSITIONS = {
    (Course.StatusChoices.DRAFT, Course.StatusChoices.REVIEW),
    (Course.StatusChoices.REVIEW, Course.StatusChoices.DRAFT),
    (Course.StatusChoices.NEEDS_REVISION, Course.StatusChoices.DRAFT),
    (Course.StatusChoices.NEEDS_REVISION, Course.StatusChoices.REVIEW),
    (Course.StatusChoices.PUBLISHED, Course.StatusChoices.ARCHIVED),
    (Course.StatusChoices.PUBLISHED, Course.StatusChoices.HIDDEN),
    (Course.StatusChoices.HIDDEN, Course.StatusChoices.ARCHIVED),
    (Course.StatusChoices.HIDDEN, Course.StatusChoices.PUBLISHED),
    (Course.StatusChoices.ARCHIVED, Course.StatusChoices.DRAFT),
}


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source="category",
        required=False,
        allow_null=True,
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        source="tags",
        required=False,
    )

    class Meta:
        model = Course
        fields = [
            "image", "title", "subtitle", "short_description", "full_description",
            "teacher_profile", "category_id",
            "level", "language", "mode", "delivery_type", "course_type",
            "duration_hours", "lessons_count",
            "with_certificate", "certificate_description", "is_on_sale", "passing_score",
            "status", "tag_ids",
        ]
        read_only_fields = ["lessons_count", "duration_hours"]

    def validate_full_description(self, value):
        return sanitize_html(value)

    def validate_status(self, value):
        if value == Course.StatusChoices.PENDING_EDIT:
            raise serializers.ValidationError(
                "This status is managed internally when a published course is edited "
                "and cannot be set directly."
            )

        request = self.context.get("request")
        is_admin = bool(
            request and request.user and request.user.is_authenticated
            and request.user.role == User.RoleChoices.ADMINISTRATOR
        )
        if is_admin:
            return value

        if self.instance is None:
            if value != Course.StatusChoices.DRAFT:
                raise serializers.ValidationError("New courses must be created as draft.")
            return value

        current = self.instance.status
        if value != current and (current, value) not in _TEACHER_ALLOWED_STATUS_TRANSITIONS:
            raise serializers.ValidationError(
                f"Cannot change status from '{current}' to '{value}' directly."
            )
        return value

    def validate(self, attrs):
        mode = attrs.get("mode", getattr(self.instance, "mode", None))
        delivery_type = attrs.get(
            "delivery_type",
            getattr(self.instance, "delivery_type", None),
        )

        if mode == Course.ModeChoices.SELF_LEARNING and delivery_type not in {
            Course.DeliveryTypeChoices.SELF_PACED,
            Course.DeliveryTypeChoices.SCHEDULED,
        }:
            raise serializers.ValidationError(
                {
                    "delivery_type": (
                        "For self_learning courses, delivery_type must be "
                        "self_paced or scheduled."
                    )
                }
            )

        if mode == Course.ModeChoices.WITH_TEACHER and delivery_type not in {
            Course.DeliveryTypeChoices.INDIVIDUAL,
            Course.DeliveryTypeChoices.GROUP,
        }:
            raise serializers.ValidationError(
                {
                    "delivery_type": (
                        "For with_teacher courses, delivery_type must be "
                        "individual or group."
                    )
                }
            )

        if attrs.get("with_certificate") is True and not (
            self.instance and self.instance.with_certificate
        ):
            teacher_profile = attrs.get("teacher_profile") or getattr(
                self.instance, "teacher_profile", None,
            )
            if teacher_profile and not teacher_profile.signature:
                raise serializers.ValidationError(
                    {
                        "with_certificate": (
                            "Upload a signature in your teacher profile before "
                            "enabling certificates."
                        )
                    }
                )

            certificate_description = attrs.get(
                "certificate_description",
                getattr(self.instance, "certificate_description", ""),
            )
            if not certificate_description.strip():
                raise serializers.ValidationError(
                    {
                        "certificate_description": (
                            "Describe what the student mastered before enabling "
                            "certificates -- it's printed on the certificate."
                        )
                    }
                )

        return attrs
