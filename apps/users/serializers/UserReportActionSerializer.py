from rest_framework import serializers

from apps.users.models import UserReportAction

from .UserReportParticipantSerializer import UserReportParticipantSerializer


class UserReportActionSerializer(serializers.ModelSerializer):
    actor = UserReportParticipantSerializer(read_only=True)

    class Meta:
        model = UserReportAction
        fields = [
            "id",
            "actor",
            "actor_role",
            "action",
            "previous_status",
            "new_status",
            "note",
            "created_at",
        ]
        read_only_fields = fields
