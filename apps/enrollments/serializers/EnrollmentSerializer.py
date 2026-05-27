from rest_framework import serializers

from apps.enrollments.models import Enrollment


class EnrollmentSerializer(serializers.ModelSerializer):
    student_profile_id = serializers.IntegerField(read_only=True)
    student_email = serializers.EmailField(source="student_profile.user.email", read_only=True)
    course_id = serializers.IntegerField(read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    course_slug = serializers.SlugField(source="course.slug", read_only=True)
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
            "order_id",
            "access_status",
            "access_granted_at",
            "access_until",
            "has_active_access",
        ]
