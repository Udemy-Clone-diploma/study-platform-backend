from rest_framework import serializers

from apps.courses.models import Category


class PublicCategorySerializer(serializers.ModelSerializer):
    courses_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "courses_count"]
        read_only_fields = fields
