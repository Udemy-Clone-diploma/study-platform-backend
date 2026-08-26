from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.courses.models import CohortMember


class CohortMemberSerializer(serializers.ModelSerializer):
    enrollment_id = serializers.IntegerField(source="enrollment.id", read_only=True)
    student_id = serializers.IntegerField(
        source="enrollment.student_profile.user.id", read_only=True
    )
    student_name = serializers.CharField(
        source="enrollment.student_profile.user.get_full_name", read_only=True
    )
    student_email = serializers.EmailField(
        source="enrollment.student_profile.user.email", read_only=True
    )
    student_avatar = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = CohortMember
        fields = [
            "id",
            "enrollment_id",
            "student_id",
            "student_name",
            "student_email",
            "student_avatar",
            "joined_at",
            "is_completed",
        ]

    def get_student_avatar(self, obj) -> str | None:
        return absolute_media_url(
            obj.enrollment.student_profile.user.avatar, self.context.get("request")
        )

    def get_is_completed(self, obj) -> bool:
        from apps.enrollments.models import CourseCompletion

        return CourseCompletion.objects.filter(
            student_profile=obj.enrollment.student_profile,
            course=obj.enrollment.course,
        ).exists()


class EnrolledStudentSerializer(serializers.Serializer):
    enrollment_id = serializers.IntegerField(source="id")
    student_id = serializers.IntegerField(source="student_profile.user.id")
    student_name = serializers.CharField(source="student_profile.user.get_full_name")
    student_email = serializers.EmailField(source="student_profile.user.email")
    student_avatar = serializers.SerializerMethodField()
    access_granted_at = serializers.DateTimeField()
    access_until = serializers.DateTimeField(allow_null=True)
    format_type = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()

    def get_student_avatar(self, obj) -> str | None:
        return absolute_media_url(obj.student_profile.user.avatar, self.context.get("request"))

    def get_format_type(self, obj):
        return obj.delivery_format.format_type if obj.delivery_format_id else None

    def get_progress_percent(self, obj):
        total = obj.course.lessons_count
        if not total:
            return 0
        return round(obj.lessons_completed_count / total * 100)

    def get_is_completed(self, obj) -> bool:
        # Completion threshold is teacher-defined and not always 100% lesson
        # progress, so this checks for an actual CourseCompletion record
        # rather than deriving it from progress_percent. The view precomputes
        # `completed_student_profile_ids` in context to avoid one query per row.
        completed_ids = self.context.get("completed_student_profile_ids")
        if completed_ids is not None:
            return obj.student_profile_id in completed_ids
        from apps.enrollments.models import CourseCompletion

        return CourseCompletion.objects.filter(
            student_profile=obj.student_profile,
            course=obj.course,
        ).exists()
