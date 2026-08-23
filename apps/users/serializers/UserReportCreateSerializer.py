from rest_framework import serializers

from apps.users.models import UserReport


class UserReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserReport
        fields = ["reason", "details"]
