from rest_framework import serializers

from apps.blog.models import BlogCategory


class BlogCategorySerializer(serializers.ModelSerializer):
    # Populated by BlogCategoryService.annotate_articles_count; DRF omits the key
    # when the serializer runs on an instance without the annotation (e.g. the
    # category embedded in article payloads).
    articles_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = BlogCategory
        fields = ["id", "name", "slug", "headline", "description", "order", "articles_count"]


class BlogCategoryCreateUpdateSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = BlogCategory
        fields = ["name", "slug", "headline", "description", "order"]

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
