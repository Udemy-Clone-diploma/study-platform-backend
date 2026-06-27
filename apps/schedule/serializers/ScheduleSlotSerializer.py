from rest_framework import serializers

from apps.schedule.models import ScheduleSlot


class ScheduleSlotSerializer(serializers.ModelSerializer):
    is_available = serializers.BooleanField(read_only=True)
    booked_by_student = serializers.SerializerMethodField()

    class Meta:
        model  = ScheduleSlot
        fields = [
            "id",
            "day_of_week",
            "start_time",
            "end_time",
            "is_available",
            "booked_by_student",
            "is_rescheduled",
            "original_day_of_week",
            "original_start_time",
            "original_end_time",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_rescheduled",
            "original_day_of_week",
            "original_start_time",
            "original_end_time",
            "created_at",
            "updated_at",
        ]

    def get_booked_by_student(self, obj: ScheduleSlot):
        """Return minimal student info for teacher view; None for student view."""
        request = self.context.get("request")
        if not request or not obj.booked_by_id:
            return None
        from apps.users.models import User
        if request.user.role not in (User.RoleChoices.TEACHER, User.RoleChoices.ADMINISTRATOR):
            return None
        enrollment = obj.booked_by
        user = enrollment.student_profile.user
        return {
            "student_profile_id": enrollment.student_profile_id,
            "full_name": user.get_full_name(),
            "email": user.email,
        }

    def validate(self, attrs):
        start = attrs.get("start_time")
        end   = attrs.get("end_time")
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_time": "end_time must be after start_time."}
            )
        return attrs


class ScheduleSlotWriteSerializer(serializers.Serializer):
    day_of_week = serializers.IntegerField(min_value=0, max_value=6)
    start_time  = serializers.TimeField()
    end_time    = serializers.TimeField()

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError(
                {"end_time": "end_time must be after start_time."}
            )
        return attrs


class ScheduleSlotRescheduleSerializer(serializers.Serializer):
    day_of_week = serializers.IntegerField(min_value=0, max_value=6, required=False)
    start_time  = serializers.TimeField(required=False)
    end_time    = serializers.TimeField(required=False)

    def validate(self, attrs):
        start = attrs.get("start_time")
        end   = attrs.get("end_time")
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_time": "end_time must be after start_time."}
            )
        return attrs
