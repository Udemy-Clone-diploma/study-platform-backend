from rest_framework import serializers

from apps.courses.models import CourseDeliveryFormat, PricingPlan


class NestedPricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingPlan
        fields = ["id", "price", "currency", "installment_count", "installment_amount"]


class CourseDeliveryFormatSerializer(serializers.ModelSerializer):
    pricing = NestedPricingSerializer(read_only=True)
    enrolled_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseDeliveryFormat
        fields = [
            "id", "format_type",
            "start_type", "course_start_date", "access_duration_days",
            "start_date", "enrollment_deadline", "unlock_mode",
            "max_students", "enrolled_count",
            "pricing",
        ]

    def get_enrolled_count(self, obj) -> int:
        from apps.enrollments.models import Enrollment
        return Enrollment.objects.filter(
            delivery_format=obj,
            access_status=Enrollment.AccessStatusChoices.ACTIVE,
        ).count()


class CourseDeliveryFormatWriteSerializer(serializers.ModelSerializer):
    """Used for create / partial-update; pricing is written separately via nested data."""

    pricing = NestedPricingSerializer(required=False, allow_null=True)

    class Meta:
        model = CourseDeliveryFormat
        fields = [
            "format_type",
            "start_type", "course_start_date", "access_duration_days",
            "start_date", "enrollment_deadline", "unlock_mode",
            "max_students",
            "pricing",
        ]
