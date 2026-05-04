from decimal import Decimal

from django.utils.text import slugify
from django.db import transaction

from apps.courses.constants import (
    DEFAULT_FEATURED_CATEGORIES_LIMIT,
    DEFAULT_NEW_COURSES_LIMIT,
    DEFAULT_POPULAR_COURSES_LIMIT,
)
from apps.courses.exceptions import InvalidPricingError
from apps.courses.models import Category, Course
from apps.courses.serializers import (
    CategorySerializer,
    CourseCreateUpdateSerializer,
    CourseDetailSerializer,
    CourseListSerializer,
)


class CourseService:
    @staticmethod
    def validate_course_data(
        data: dict,
        course: Course | None = None,
        partial: bool = False,
        context: dict | None = None,
    ) -> dict:
        serializer = CourseCreateUpdateSerializer(
            course,
            data=data,
            partial=partial,
            context=context or {},
        )
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data #type: ignore

    @staticmethod
    def serialize_course_detail(
        course: Course,
        context: dict | None = None,
    ) -> dict:
        return CourseDetailSerializer(course, context=context or {}).data #type: ignore

    @classmethod
    def create_course_from_data(
        cls,
        data: dict,
        context: dict | None = None,
    ) -> dict:
        validated_data = cls.validate_course_data(data, context=context)
        course = cls.create_course(validated_data)
        return cls.serialize_course_detail(course, context=context)

    @classmethod
    def update_course_from_data(
        cls,
        course: Course,
        data: dict,
        partial: bool = True,
        context: dict | None = None,
    ) -> dict:
        validated_data = cls.validate_course_data(
            data,
            course=course,
            partial=partial,
            context=context,
        )
        course = cls.update_course(course, validated_data)
        return cls.serialize_course_detail(course, context=context)

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
            validated_data["slug"] = cls._build_unique_slug(title, None) #type: ignore
            return validated_data

        title_changed = "title" in validated_data and validated_data["title"] != course.title
        can_regenerate_slug = (
            course.status == Course.StatusChoices.DRAFT and title_changed
        )

        if can_regenerate_slug:
            validated_data["slug"] = cls._build_unique_slug(title, course) #type: ignore

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

        if pricing_type == Course.PricingTypeChoices.FREE:
            validated_data["price"] = Decimal("0.00")
            validated_data["installment_count"] = None
            validated_data["installment_amount"] = None
            return validated_data

        if pricing_type == Course.PricingTypeChoices.FULL_PAYMENT:
            if price is None or price <= 0:
                raise InvalidPricingError(
                    "Price must be greater than 0 for fully paid courses."
                )
            validated_data["installment_count"] = None
            validated_data["installment_amount"] = None
            return validated_data


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

    @staticmethod
    def get_new_courses(limit: int = DEFAULT_NEW_COURSES_LIMIT) -> list[dict]:
        courses = Course.objects.filter(
            status=Course.StatusChoices.PUBLISHED, is_deleted=False
        ).order_by('-published_at')[:limit]
        return CourseListSerializer(courses, many=True).data

    @staticmethod
    def get_popular_courses(limit: int = DEFAULT_POPULAR_COURSES_LIMIT) -> list[dict]:
        courses = Course.objects.filter(
            status=Course.StatusChoices.PUBLISHED, is_deleted=False
        ).order_by('-rating_avg')[:limit]
        return CourseListSerializer(courses, many=True).data

    @staticmethod
    def get_categories(limit: int = DEFAULT_FEATURED_CATEGORIES_LIMIT) -> list[dict]:
        categories = Category.objects.all()[:limit]
        return CategorySerializer(categories, many=True).data

