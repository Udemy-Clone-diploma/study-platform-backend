from rest_framework import serializers

from apps.common.sanitize import sanitize_html
from apps.courses.models import Category, Course, Tag


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
            "teacher_profile", "moderator_profile", "category_id",
            "level", "language", "mode", "delivery_type", "course_type",
            "duration_hours", "lessons_count",
            "with_certificate", "is_on_sale",
            "status", "tag_ids",
        ]
        read_only_fields = ["lessons_count", "duration_hours"]

    def validate_full_description(self, value):
        return sanitize_html(value)

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

        return attrs
