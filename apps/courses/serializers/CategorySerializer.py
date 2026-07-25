from rest_framework import serializers

from apps.common.i18n import localized_field, resolve_locale
from apps.courses.models import Category


class CategorySerializer(serializers.ModelSerializer):
    """Public read shape: name/description resolved to the request's ?lang= locale."""

    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    # Populated by CategoryService.annotate_courses_count; DRF omits the key
    # when the serializer runs on an instance without the annotation (e.g.
    # the category embedded in course payloads).
    courses_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "courses_count", "featured_order"]

    def get_name(self, obj):
        return localized_field(obj, "name", resolve_locale(self.context.get("request")))

    def get_description(self, obj):
        return localized_field(obj, "description", resolve_locale(self.context.get("request")))


class CategoryWriteSerializer(serializers.ModelSerializer):
    """Admin write shape: exposes every locale field directly for create/update."""

    slug = serializers.SlugField(max_length=50, required=False, allow_blank=True)
    courses_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "slug",
            "courses_count",
            "featured_order",
            "name_en",
            "name_uk",
            "name_fr",
            "name_es",
            "name_de",
            "description_en",
            "description_uk",
            "description_fr",
            "description_es",
            "description_de",
        ]

    # Both uniqueness checks run against all_objects because the DB unique
    # constraints span soft-deleted rows; validating only active rows would
    # let a duplicate through to an IntegrityError 500. name_en is the
    # canonical identifier (see apps.common.i18n / Category.__str__).
    def validate_name_en(self, value):
        qs = Category.all_objects.filter(name_en__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value

    def validate_slug(self, value):
        if not value:
            return value
        qs = Category.all_objects.filter(slug=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A category with this slug already exists.")
        return value
