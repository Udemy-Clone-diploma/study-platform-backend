from rest_framework import serializers

from apps.courses.models import Tag


class PublicTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name"]
        read_only_fields = fields
