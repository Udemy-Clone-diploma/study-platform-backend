from rest_framework import serializers

from apps.courses.models import Cohort, CohortMember
from apps.courses.serializers.CohortGroupSerializer import CohortMemberSerializer


class CohortSerializer(serializers.ModelSerializer):
    members = CohortMemberSerializer(many=True, read_only=True)
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
            "members",
        ]

    def get_members_count(self, obj):
        # len(), not .count(): reuses the prefetched "members" cache instead of
        # firing a fresh COUNT query per cohort when members are already loaded.
        return len(obj.members.all())
