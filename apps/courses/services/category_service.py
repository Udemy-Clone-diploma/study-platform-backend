from django.db.models import Count, Q, QuerySet
from django.utils.text import slugify

from apps.courses.exceptions import CategoryInUseError
from apps.courses.models import Category

SLUG_MAX_LENGTH = Category._meta.get_field("slug").max_length
NAME_MAX_LENGTH = Category._meta.get_field("name_en").max_length


class CategoryService:
    @staticmethod
    def annotate_courses_count(queryset: QuerySet) -> QuerySet:
        # Reverse-FK annotations bypass ActiveManager, so soft-deleted
        # courses must be excluded explicitly.
        return queryset.annotate(
            courses_count=Count("courses", filter=Q(courses__is_deleted=False))
        )

    @staticmethod
    def annotate_public_courses_count(queryset: QuerySet) -> QuerySet:
        return queryset.annotate(
            courses_count=Count(
                "courses",
                filter=Q(
                    courses__is_deleted=False,
                    courses__status="published",
                ),
            )
        )

    @classmethod
    def create_category(cls, validated_data: dict) -> Category:
        if not validated_data.get("slug"):
            validated_data["slug"] = cls._generate_unique_slug(validated_data["name_en"])
        return Category.objects.create(**validated_data)

    @classmethod
    def update_category(cls, category: Category, validated_data: dict) -> Category:
        if "slug" in validated_data and not validated_data["slug"]:
            validated_data["slug"] = cls._generate_unique_slug(
                validated_data.get("name_en", category.name_en), exclude_pk=category.pk
            )
        for field, value in validated_data.items():
            setattr(category, field, value)
        category.save()
        return category

    @staticmethod
    def delete_category(category: Category) -> None:
        count = category.courses.count()
        if count:
            noun = "course" if count == 1 else "courses"
            raise CategoryInUseError(
                f"Category is assigned to {count} {noun}. Move them first."
            )
        # name_en/slug uniqueness spans soft-deleted rows (see _generate_unique_slug),
        # so free the name up for reuse by mangling the deleted row's own copy. The
        # pk suffix keeps it unique even if the same name gets deleted more than once.
        suffix = f"-deleted-{category.pk}"
        category.name_en = f"{category.name_en}{suffix}"[:NAME_MAX_LENGTH]
        category.slug = f"{category.slug[: SLUG_MAX_LENGTH - len(suffix)]}{suffix}"
        category.is_deleted = True
        category.save(update_fields=["name_en", "slug", "is_deleted"])

    @staticmethod
    def _generate_unique_slug(name: str, exclude_pk: int | None = None) -> str:
        # Uniqueness is checked against all_objects because the DB unique
        # constraint on slug spans soft-deleted rows too.
        base = slugify(name)[:SLUG_MAX_LENGTH] or "category"
        candidates = Category.all_objects.all()
        if exclude_pk is not None:
            candidates = candidates.exclude(pk=exclude_pk)
        slug = base
        suffix = 2
        while candidates.filter(slug=slug).exists():
            tail = f"-{suffix}"
            slug = base[: SLUG_MAX_LENGTH - len(tail)] + tail
            suffix += 1
        return slug
