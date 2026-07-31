from rest_framework import serializers

from apps.courses.models import CourseDeliveryFormat, PricingPlan


class NestedPricingSerializer(serializers.ModelSerializer):
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    final_installment_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, allow_null=True,
    )

    class Meta:
        model = PricingPlan
        fields = [
            "id", "price", "final_price", "currency",
            "installment_count", "installment_amount", "final_installment_amount",
        ]


class CourseDeliveryFormatSerializer(serializers.ModelSerializer):
    pricing = NestedPricingSerializer(read_only=True)
    enrolled_count = serializers.SerializerMethodField()
    completed_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseDeliveryFormat
        fields = [
            "id", "format_type",
            "start_type", "course_start_date", "access_duration_days",
            "start_date", "enrollment_deadline", "unlock_mode",
            "max_students", "enrolled_count", "completed_count",
            "pricing",
        ]

    def get_enrolled_count(self, obj) -> int:
        # `annotated_enrolled_count` is set by CourseService.delivery_formats_prefetch
        # on list/detail querysets so this avoids one COUNT query per delivery
        # format; views that serialize a single fetched-by-pk instance (create/
        # update responses) fall back to a direct count.
        if hasattr(obj, "annotated_enrolled_count"):
            return obj.annotated_enrolled_count

        from apps.enrollments.models import Enrollment
        return Enrollment.objects.filter(
            delivery_format=obj,
            access_status=Enrollment.AccessStatusChoices.ACTIVE,
        ).count()

    def get_completed_count(self, obj) -> int:
        # Same pre-annotation pattern as get_enrolled_count -- how many of this
        # format's actively-enrolled students have a CourseCompletion record for
        # the course (completion threshold is teacher-defined, not always 100%
        # lesson progress, so this can't be derived from progress_percent alone).
        if hasattr(obj, "annotated_completed_count"):
            return obj.annotated_completed_count

        from apps.enrollments.models import Enrollment
        return Enrollment.objects.filter(
            delivery_format=obj,
            access_status=Enrollment.AccessStatusChoices.ACTIVE,
            student_profile__course_completions__course=obj.course,
        ).distinct().count()


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
