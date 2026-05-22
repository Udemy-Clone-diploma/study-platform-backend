from django.utils import timezone
from rest_framework import serializers

from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from apps.users.models import StudentProfile


class EnrollmentSerializer(serializers.ModelSerializer):
    student_profile_id = serializers.IntegerField(read_only=True)
    student_email = serializers.EmailField(source="student_profile.user.email", read_only=True)
    course_id = serializers.IntegerField(read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    course_slug = serializers.SlugField(source="course.slug", read_only=True)
    id_order = serializers.IntegerField(source="order_id", read_only=True, allow_null=True)
    has_active_access = serializers.BooleanField(read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "student_profile_id",
            "student_email",
            "course_id",
            "course_title",
            "course_slug",
            "id_order",
            "access_status",
            "access_granted_at",
            "access_until",
            "has_active_access",
        ]


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
    id_order = serializers.IntegerField(
        source="order_id",
        min_value=1,
        required=False,
        allow_null=True,
    )
    access_status = serializers.ChoiceField(
        choices=Enrollment.AccessStatusChoices.choices,
        required=False,
    )
    access_until = serializers.DateTimeField(required=False, allow_null=True)

    def validate_access_until(self, value):
        if value is not None and value < timezone.now():
            raise serializers.ValidationError("Access end date cannot be in the past.")
        return value


class EnrollmentUpdateSerializer(serializers.Serializer):
    id_order = serializers.IntegerField(
        source="order_id",
        min_value=1,
        required=False,
        allow_null=True,
    )
    access_status = serializers.ChoiceField(
        choices=Enrollment.AccessStatusChoices.choices,
        required=False,
    )
    access_until = serializers.DateTimeField(required=False, allow_null=True)
