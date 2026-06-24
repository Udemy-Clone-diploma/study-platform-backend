from rest_framework import serializers

from apps.courses.models import TeacherUnavailability


class TeacherUnavailabilitySerializer(serializers.ModelSerializer):
    day_of_week_display   = serializers.CharField(source="get_day_of_week_display", read_only=True)
    recurrence_type_display = serializers.CharField(source="get_recurrence_type_display", read_only=True)

    class Meta:
        model  = TeacherUnavailability
        fields = [
            "id",
            "recurrence_type",
            "recurrence_type_display",
            "day_of_week",
            "day_of_week_display",
            "date",
            "date_to",
            "start_time",
            "end_time",
            "reason",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "day_of_week_display",
            "recurrence_type_display",
            "created_at",
        ]


class TeacherUnavailabilityWriteSerializer(serializers.Serializer):
    recurrence_type = serializers.ChoiceField(
        choices=TeacherUnavailability.RecurrenceType.choices
    )
    day_of_week = serializers.IntegerField(min_value=0, max_value=6, required=False)
    date        = serializers.DateField(required=False, allow_null=True)
    date_to     = serializers.DateField(required=False, allow_null=True)
    start_time  = serializers.TimeField()
    end_time    = serializers.TimeField()
    reason      = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError(
                {"end_time": "end_time must be after start_time."}
            )
        recurrence = attrs["recurrence_type"]
        if recurrence == TeacherUnavailability.RecurrenceType.ONE_TIME:
            if not attrs.get("date"):
                raise serializers.ValidationError(
                    {"date": "date is required for one_time unavailability."}
                )
        elif recurrence == TeacherUnavailability.RecurrenceType.DATE_RANGE:
            if not attrs.get("date"):
                raise serializers.ValidationError(
                    {"date": "date (start date) is required for date_range unavailability."}
                )
            if not attrs.get("date_to"):
                raise serializers.ValidationError(
                    {"date_to": "date_to (end date) is required for date_range unavailability."}
                )
            if attrs["date_to"] < attrs["date"]:
                raise serializers.ValidationError(
                    {"date_to": "date_to must be on or after date."}
                )
        else:
            if attrs.get("day_of_week") is None:
                raise serializers.ValidationError(
                    {"day_of_week": "day_of_week is required for weekly unavailability."}
                )
        return attrs
