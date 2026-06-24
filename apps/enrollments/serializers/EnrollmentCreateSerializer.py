from django.utils import timezone
from rest_framework import serializers

from apps.courses.models import Course, CourseDeliveryFormat
from apps.enrollments.models import Enrollment
from apps.users.models import StudentProfile


class EnrollmentCreateSerializer(serializers.Serializer):
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.all(),
        source="course",
        write_only=True,
    )
    student_profile_id = serializers.PrimaryKeyRelatedField(
        queryset=StudentProfile.objects.select_related("user"),
        source="student_profile",
        required=False,
        write_only=True,
    )
    order_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
    )
    access_status = serializers.ChoiceField(
        choices=Enrollment.AccessStatusChoices.choices,
        required=False,
    )
    access_until = serializers.DateTimeField(required=False, allow_null=True)
    delivery_format_id = serializers.PrimaryKeyRelatedField(
        queryset=CourseDeliveryFormat.objects.all(),
        source="delivery_format",
        required=False,
        allow_null=True,
    )
    # Optional: provided when student buys an individual-format course and picks a time slot.
    schedule_slot_id = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
    )

    def validate_access_until(self, value):
        if value is not None and value < timezone.now():
            raise serializers.ValidationError("Access end date cannot be in the past.")
        return value
