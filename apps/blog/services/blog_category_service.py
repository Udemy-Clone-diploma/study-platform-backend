from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.utils import timezone
from django.utils.text import slugify

from apps.blog.exceptions import BlogCategoryInUseError
from apps.blog.models import Article, BlogCategory

SLUG_MAX_LENGTH = BlogCategory._meta.get_field("slug").max_length


class BlogCategoryService:
    @staticmethod
    def annotate_articles_count(queryset: QuerySet) -> QuerySet:
        # Reverse-FK annotations bypass ActiveManager, so soft-deleted
        # articles must be excluded explicitly.
        return queryset.annotate(
            articles_count=Count(
                "articles",
                filter=Q(
                    articles__is_deleted=False,
                    articles__status=Article.StatusChoices.PUBLISHED,
                ),
            ),
        )

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

    @classmethod
    @transaction.atomic
    def delete_category(
        cls,
        category: BlogCategory,
        *,
        archive_articles: bool = False,
        move_to: BlogCategory | None = None,
    ) -> None:
        articles = Article.objects.filter(category=category)
        count = articles.count()
        if count:
            if archive_articles:
                articles.update(status=Article.StatusChoices.ARCHIVED, updated_at=timezone.now())
            elif move_to is not None:
                articles.update(category=move_to, updated_at=timezone.now())
            else:
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
