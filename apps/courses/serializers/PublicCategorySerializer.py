from rest_framework import serializers

from apps.common.i18n import localized_field, resolve_locale
from apps.courses.models import Category


class PublicCategorySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    courses_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "courses_count"]
        read_only_fields = fields

    def get_name(self, obj: Category) -> str:
        return localized_field(
            obj,
            "name",
            resolve_locale(self.context.get("request")),
        )

    def get_description(self, obj: Category) -> str:
        return localized_field(
            obj,
            "description",
            resolve_locale(self.context.get("request")),
        )
