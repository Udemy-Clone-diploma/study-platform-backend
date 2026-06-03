from rest_framework import serializers

from apps.curriculum.models import Module


class ModuleCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ["title", "description"]
        extra_kwargs = {
            "description": {"required": False},
        }
