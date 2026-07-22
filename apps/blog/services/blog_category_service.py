from django.utils.text import slugify

from apps.blog.exceptions import BlogCategoryInUseError
from apps.blog.models import Article, BlogCategory

SLUG_MAX_LENGTH = BlogCategory._meta.get_field("slug").max_length


class BlogCategoryService:
    @classmethod
    def create_category(cls, validated_data: dict) -> BlogCategory:
        if not validated_data.get("slug"):
            validated_data["slug"] = cls._generate_unique_slug(validated_data["name"])
        return BlogCategory.objects.create(**validated_data)

    @classmethod
    def update_category(cls, category: BlogCategory, validated_data: dict) -> BlogCategory:
        if "slug" in validated_data and not validated_data["slug"]:
            validated_data["slug"] = cls._generate_unique_slug(
                validated_data.get("name", category.name), exclude_pk=category.pk,
            )
        for field, value in validated_data.items():
            setattr(category, field, value)
        category.save()
        return category

    @staticmethod
    def delete_category(category: BlogCategory) -> None:
        count = Article.objects.filter(category=category).count()
        if count:
            noun = "article" if count == 1 else "articles"
            raise BlogCategoryInUseError(
                f"Category is assigned to {count} {noun}. Move them first.",
            )
        category.is_deleted = True
        category.save(update_fields=["is_deleted"])

    @staticmethod
    def _generate_unique_slug(name: str, exclude_pk: int | None = None) -> str:
        base = slugify(name)[:SLUG_MAX_LENGTH] or "category"
        candidates = BlogCategory.all_objects.all()
        if exclude_pk is not None:
            candidates = candidates.exclude(pk=exclude_pk)
        slug = base
        suffix = 2
        while candidates.filter(slug=slug).exists():
            tail = f"-{suffix}"
            slug = base[: SLUG_MAX_LENGTH - len(tail)] + tail
            suffix += 1
        return slug
