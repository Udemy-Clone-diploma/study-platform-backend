from rest_framework import serializers

from apps.users.models import ModeratorProfile


class ModeratorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeratorProfile
        fields = ["level"]
