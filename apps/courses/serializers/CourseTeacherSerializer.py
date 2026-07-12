from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.users.models import TeacherProfile


class CourseTeacherSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.get_full_name", read_only=True)
    avatar = serializers.SerializerMethodField()
    students_taught = serializers.SerializerMethodField()

    class Meta:
        model = TeacherProfile
        fields = [
            "id", "name", "avatar", "bio", "specialization",
            "years_experience", "partnerships_count", "students_taught",
        ]

    def get_avatar(self, obj: TeacherProfile) -> str | None:
        return absolute_media_url(obj.user.avatar, self.context.get("request"))

    def get_students_taught(self, obj: TeacherProfile) -> int:
        """Distinct students with active access across every course this teacher owns —
        computed live so it always reflects current enrollments, not a stale stored count."""
        from apps.enrollments.models import Enrollment

        return (
            Enrollment.objects.with_active_access()
            .filter(course__teacher_profile=obj)
            .values("student_profile_id")
            .distinct()
            .count()
        )
