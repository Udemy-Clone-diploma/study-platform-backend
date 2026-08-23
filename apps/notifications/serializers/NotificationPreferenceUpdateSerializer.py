from rest_framework import serializers

from apps.notifications.models import Notification
from apps.notifications.preferences import CHANNELS


class NotificationPreferenceUpdateSerializer(serializers.Serializer):
    """Validates a partial `{type: {channel: bool}}` preference patch.

    Output is the cleaned override fragment; unknown types or channels are
    rejected so a typo never silently becomes a stored no-op.
    """

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Expected an object mapping notification type to channel toggles."
                    ]
                }
            )

        valid_types = set(Notification.TypeChoices.values)
        cleaned = {}
        for ntype, channels in data.items():
            if ntype not in valid_types:
                raise serializers.ValidationError({ntype: "Unknown notification type."})
            if not isinstance(channels, dict):
                raise serializers.ValidationError({ntype: "Expected an object of channel toggles."})
            entry = {}
            for channel, value in channels.items():
                if channel not in CHANNELS:
                    raise serializers.ValidationError({ntype: f"Unknown channel '{channel}'."})
                if not isinstance(value, bool):
                    raise serializers.ValidationError({ntype: f"'{channel}' must be a boolean."})
                entry[channel] = value
            if entry:
                cleaned[ntype] = entry
        return cleaned
