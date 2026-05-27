from rest_framework import serializers

from apps.courses.models import Cohort


class CohortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cohort
        fields = [
            "id",
            "duration_months",
            "hours_per_week_min",
            "hours_per_week_max",
            "group_size",
            "delivery_mode",
            "start_date",
        ]

    def validate(self, attrs):
        hours_min = attrs.get(
            "hours_per_week_min",
            getattr(self.instance, "hours_per_week_min", None),
        )
        hours_max = attrs.get(
            "hours_per_week_max",
            getattr(self.instance, "hours_per_week_max", None),
        )
        if hours_min is not None and hours_max is not None and hours_min > hours_max:
            raise serializers.ValidationError(
                {"hours_per_week_min": "hours_per_week_min cannot exceed hours_per_week_max."}
            )
        return attrs
