from rest_framework import serializers

from apps.courses.models import Category


class CategorySerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(max_length=50, required=False, allow_blank=True)
    # Populated by CategoryService.annotate_courses_count; DRF omits the key
    # when the serializer runs on an instance without the annotation (e.g.
    # the category embedded in course payloads).
    courses_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "courses_count", "featured_order"]

    # Both uniqueness checks run against all_objects because the DB unique
    # constraints span soft-deleted rows; validating only active rows would
    # let a duplicate through to an IntegrityError 500.
    def validate_name(self, value):
        qs = Category.all_objects.filter(name__iexact=value)
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
