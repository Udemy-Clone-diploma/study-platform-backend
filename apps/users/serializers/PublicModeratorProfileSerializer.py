from rest_framework import serializers

from apps.users.models import ModeratorProfile


class PublicModeratorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeratorProfile
        fields = ["level"]
        read_only_fields = fields
