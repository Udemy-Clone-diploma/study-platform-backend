from rest_framework import serializers

from apps.courses.models import CohortSchedule


class CohortScheduleSerializer(serializers.ModelSerializer):
    day_of_week_display = serializers.CharField(
        source="get_day_of_week_display", read_only=True
    )

    class Meta:
        model  = CohortSchedule
        fields = [
            "id",
            "day_of_week",
            "day_of_week_display",
            "start_time",
            "end_time",
            "meeting_link",
            "created_at",
        ]
        read_only_fields = ["id", "day_of_week_display", "created_at"]

    def validate(self, attrs):
        start = attrs.get("start_time")
        end   = attrs.get("end_time")
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_time": "end_time must be after start_time."}
            )
        return attrs


class CohortScheduleWriteSerializer(serializers.Serializer):
    day_of_week  = serializers.IntegerField(min_value=0, max_value=6)
    start_time   = serializers.TimeField()
    end_time     = serializers.TimeField()
    meeting_link = serializers.URLField(required=False, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError(
                {"end_time": "end_time must be after start_time."}
            )
        return attrs
