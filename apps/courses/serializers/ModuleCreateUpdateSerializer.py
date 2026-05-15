from rest_framework import serializers

from apps.courses.models import Module


class ModuleCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ["title"]
