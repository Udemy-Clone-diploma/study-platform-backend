from rest_framework import serializers

from apps.courses.models import CourseDeliveryFormat

from .PublicPricingPlanSerializer import PublicPricingPlanSerializer


class PublicCourseDeliveryFormatSerializer(serializers.ModelSerializer):
    pricing = PublicPricingPlanSerializer(read_only=True)
    enrolled_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseDeliveryFormat
        fields = [
            "id",
            "format_type",
            "start_type",
            "course_start_date",
            "access_duration_days",
            "start_date",
            "enrollment_deadline",
            "unlock_mode",
            "max_students",
            "enrolled_count",
            "pricing",
        ]
        read_only_fields = fields

    def get_enrolled_count(self, obj: CourseDeliveryFormat) -> int:
        if hasattr(obj, "annotated_enrolled_count"):
            return obj.annotated_enrolled_count

        from apps.enrollments.models import Enrollment

        return Enrollment.objects.filter(
            delivery_format=obj,
            access_status=Enrollment.AccessStatusChoices.ACTIVE,
        ).count()
