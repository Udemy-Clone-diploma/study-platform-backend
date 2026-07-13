from rest_framework import serializers


class UserBlockSerializer(serializers.Serializer):
    is_blocked = serializers.BooleanField()
