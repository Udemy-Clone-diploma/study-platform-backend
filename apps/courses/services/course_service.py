from decimal import Decimal

from django.utils.text import slugify
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.courses.models import Course


class CourseService:
    # data validation
    @staticmethod
    def _resolve_value(
        validated_data: dict,
        field: str,
        course: Course | None,
        default=None,
    ):
        if field in validated_data:
            return validated_data[field]
        if course is not None:
            return getattr(course, field)
        return default

    # pricing rules
    @classmethod
    def _build_unique_slug(cls, base_value: str, course: Course | None = None) -> str:
        base_slug = slugify(base_value) or "course"
        candidate = base_slug
        suffix = 2

        queryset = Course.all_objects.all()
        if course is not None:
            queryset = queryset.exclude(pk=course.pk)

        while queryset.filter(slug=candidate).exists():
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

        return candidate

    @classmethod
    def _apply_slug_rules(
        cls,
        validated_data: dict,
        course: Course | None = None,
    ) -> dict:
        title = cls._resolve_value(validated_data, "title", course, "")

        if course is None:
            validated_data["slug"] = cls._build_unique_slug(title, None)
            return validated_data

        title_changed = "title" in validated_data and validated_data["title"] != course.title
        can_regenerate_slug = (
            course.status == Course.StatusChoices.DRAFT and title_changed
        )

        if can_regenerate_slug:
            validated_data["slug"] = cls._build_unique_slug(title, course)

        return validated_data

    @classmethod
    def _apply_pricing_rules(
        cls,
        validated_data: dict,
        course: Course | None = None,
    ) -> dict:
        pricing_type = cls._resolve_value(
            validated_data,
            "pricing_type",
            course,
            Course.PricingTypeChoices.FREE,
        )
        price = cls._resolve_value(
            validated_data,
            "price",
            course,
            Decimal("0.00"),
        )
        installment_count = cls._resolve_value(
            validated_data,
            "installment_count",
            course,
            None,
        )
        installment_amount = cls._resolve_value(
            validated_data,
            "installment_amount",
            course,
            None,
        )

        if pricing_type == Course.PricingTypeChoices.FREE:
            validated_data["price"] = Decimal("0.00")
            validated_data["installment_count"] = None
            validated_data["installment_amount"] = None
            return validated_data

        if pricing_type == Course.PricingTypeChoices.FULL_PAYMENT:
            if price is None or price <= 0:
                raise ValidationError(
                    {"price": "Price must be greater than 0 for fully paid courses."}
                )
            validated_data["installment_count"] = None
            validated_data["installment_amount"] = None
            return validated_data

        if pricing_type == Course.PricingTypeChoices.INSTALLMENT:
            errors = {}

            if price is None or price <= 0:
                errors["price"] = "Total course price must be greater than 0."
            if installment_count is None or installment_count <= 0:
                errors["installment_count"] = (
                    "Installment count must be greater than 0."
                )
            if installment_amount is None or installment_amount <= 0:
                errors["installment_amount"] = (
                    "Installment amount must be greater than 0."
                )

            if errors:
                raise ValidationError(errors)

        return validated_data

    @staticmethod
    @transaction.atomic
    def create_course(validated_data: dict) -> Course:
        validated_data = CourseService._apply_slug_rules(dict(validated_data))
        validated_data = CourseService._apply_pricing_rules(validated_data)
        tags = validated_data.pop("tags", [])
        course = Course.all_objects.create(**validated_data)
        if tags:
            course.tags.set(tags)
        return course

    @staticmethod
    @transaction.atomic
    def update_course(course: Course, validated_data: dict) -> Course:
        validated_data = CourseService._apply_slug_rules(
            dict(validated_data),
            course=course,
        )
        validated_data = CourseService._apply_pricing_rules(
            validated_data,
            course=course,
        )
        tags = validated_data.pop("tags", None)

        for attr, value in validated_data.items():
            setattr(course, attr, value)

        course.save()

        if tags is not None:
            course.tags.set(tags)

        return course

    @staticmethod
    @transaction.atomic
    def soft_delete_course(course: Course) -> None:
        course.is_deleted = True
        course.status = Course.StatusChoices.ARCHIVED
        course.save(update_fields=["is_deleted", "status"])
