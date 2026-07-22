from rest_framework import serializers

from apps.blog.models import BlogCategory


class BlogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = ["id", "name", "slug", "description", "order"]


class BlogCategoryCreateUpdateSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = BlogCategory
        fields = ["name", "slug", "description", "order"]

    # Both uniqueness checks run against all_objects because the DB unique
    # constraints span soft-deleted rows; validating only active rows would
    # let a duplicate through to an IntegrityError 500.
    def validate_name(self, value):
        qs = BlogCategory.all_objects.filter(name__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value

    def validate_slug(self, value):
        if not value:
            return value
        qs = BlogCategory.all_objects.filter(slug=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A category with this slug already exists.")
        return value
