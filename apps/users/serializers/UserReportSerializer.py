from copy import deepcopy

from rest_framework import serializers

from apps.users.models import UserReport

from .UserReportActionSerializer import UserReportActionSerializer
from .UserReportParticipantSerializer import UserReportParticipantSerializer


class UserReportSerializer(serializers.ModelSerializer):
    reporter = UserReportParticipantSerializer(read_only=True)
    reported_user = UserReportParticipantSerializer(read_only=True)
    assigned_moderator = serializers.SerializerMethodField()
    escalated_by = UserReportParticipantSerializer(read_only=True)
    resolved_by = UserReportParticipantSerializer(read_only=True)
    reason_label = serializers.CharField(source="get_reason_display", read_only=True)
    profile_snapshot = serializers.SerializerMethodField()
    actions = UserReportActionSerializer(many=True, read_only=True)

    class Meta:
        model = UserReport
        fields = [
            "id",
            "reporter",
            "reported_user",
            "reason",
            "reason_label",
            "details",
            "profile_snapshot",
            "status",
            "resolution",
            "assigned_moderator",
            "assigned_at",
            "escalated_by",
            "escalated_at",
            "escalation_note",
            "resolved_by",
            "resolved_at",
            "resolution_note",
            "actions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_assigned_moderator(self, obj: UserReport) -> dict | None:
        if obj.assigned_moderator_id is None:
            return None
        return UserReportParticipantSerializer(
            obj.assigned_moderator.user,
            context=self.context,
        ).data

    def get_profile_snapshot(self, obj: UserReport) -> dict:
        snapshot = deepcopy(obj.profile_snapshot)
        avatar = snapshot.get("avatar")
        request = self.context.get("request")
        if avatar and request and avatar.startswith("/"):
            snapshot["avatar"] = request.build_absolute_uri(avatar)
        return snapshot
