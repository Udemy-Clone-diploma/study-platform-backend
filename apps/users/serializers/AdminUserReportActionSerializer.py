from rest_framework import serializers


class AdminUserReportActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=["warning", "block", "unblock", "dismiss"]
    )
    note = serializers.CharField(min_length=10, max_length=500, trim_whitespace=True)
