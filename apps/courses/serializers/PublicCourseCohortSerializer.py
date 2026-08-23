from rest_framework import serializers

from apps.courses.models import Cohort


class PublicCourseCohortSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = Cohort
        fields = [
            "id",
            "delivery_format",
            "name",
            "duration_months",
            "hours_per_week",
            "group_size",
            "start_date",
            "enrollment_deadline",
            "is_enrollment_open",
            "members_count",
        ]
        read_only_fields = fields

    def get_members_count(self, obj: Cohort) -> int:
        if hasattr(obj, "annotated_members_count"):
            return obj.annotated_members_count
        return obj.members.count()
