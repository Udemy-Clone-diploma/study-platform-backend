from rest_framework import serializers

from apps.courses.models import CohortMember


class CohortMemberSerializer(serializers.ModelSerializer):
    enrollment_id = serializers.IntegerField(source="enrollment.id", read_only=True)
    student_id = serializers.IntegerField(source="enrollment.student_profile.user.id", read_only=True)
    student_name = serializers.CharField(source="enrollment.student_profile.user.get_full_name", read_only=True)
    student_email = serializers.EmailField(source="enrollment.student_profile.user.email", read_only=True)

    class Meta:
        model = CohortMember
        fields = ["id", "enrollment_id", "student_id", "student_name", "student_email", "joined_at"]


class EnrolledStudentSerializer(serializers.Serializer):
    enrollment_id = serializers.IntegerField(source="id")
    student_id = serializers.IntegerField(source="student_profile.id")
    student_name = serializers.CharField(source="student_profile.user.get_full_name")
    student_email = serializers.EmailField(source="student_profile.user.email")
    access_granted_at = serializers.DateTimeField()
    access_until = serializers.DateTimeField(allow_null=True)
    format_type = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()

    def get_format_type(self, obj):
        return obj.delivery_format.format_type if obj.delivery_format_id else None

    def get_progress_percent(self, obj):
        total = obj.course.lessons_count
        if not total:
            return 0
        return round(obj.lessons_completed_count / total * 100)
