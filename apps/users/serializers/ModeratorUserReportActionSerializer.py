from rest_framework import serializers


class ModeratorUserReportActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["warning", "block", "unblock", "escalate", "dismiss"])
    note = serializers.CharField(min_length=10, max_length=500, trim_whitespace=True)
