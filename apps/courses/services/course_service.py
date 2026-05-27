from django.db import transaction
from django.db.models import Min, Subquery, OuterRef
from django.utils.text import slugify

from apps.courses.constants import (
    DEFAULT_FEATURED_CATEGORIES_LIMIT,
    DEFAULT_NEW_COURSES_LIMIT,
    DEFAULT_POPULAR_COURSES_LIMIT,
)
from apps.courses.models import Category, Course, PricingPlan
from apps.courses.serializers import (
    CategorySerializer,
    CourseCreateUpdateSerializer,
    CourseDetailSerializer,
    CourseListSerializer,
)
from apps.users.models import User


class CourseService:
    @staticmethod
    def annotate_min_price(queryset):
        """Annotate each course with min_price and the matching min_currency.

        Courses without any PricingPlan get min_price=None, min_currency=None
        (which the catalog serializes as a free course).
        """
        cheapest_plan = (
            PricingPlan.objects.filter(course=OuterRef("pk"))
            .order_by("price")
            .values("currency")[:1]
        )
        return queryset.annotate(
            min_price=Min("pricing_plans__price"),
            min_currency=Subquery(cheapest_plan),
        )

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
        return serializer.validated_data

    @classmethod
    def serialize_course_detail(
        cls,
        course: Course,
        context: dict | None = None,
    ) -> dict:
        annotated = cls.annotate_min_price(
            Course.all_objects.filter(pk=course.pk)
        ).first()
        return CourseDetailSerializer(annotated or course, context=context or {}).data

    @classmethod
    def create_course_from_data(cls, data: dict, context: dict) -> dict:
        validated_data = cls.validate_course_data(data, context=context)
        course = cls.create_course(validated_data, request_user=context["request"].user)
        return cls.serialize_course_detail(course, context=context)

    @classmethod
    def update_course_from_data(
        cls,
        course: Course,
        data: dict,
        context: dict,
        partial: bool = True,
    ) -> dict:
        validated_data = cls.validate_course_data(
            data,
            course=course,
            partial=partial,
            context=context,
        )
        course = cls.update_course(
            course,
            validated_data,
            request_user=context["request"].user,
        )
        return cls.serialize_course_detail(course, context=context)

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
            validated_data["slug"] = cls._build_unique_slug(title, None)
            return validated_data

        title_changed = "title" in validated_data and validated_data["title"] != course.title
        can_regenerate_slug = (
            course.status == Course.StatusChoices.DRAFT and title_changed
        )

        if can_regenerate_slug:
            validated_data["slug"] = cls._build_unique_slug(title, course)

        return validated_data

    @staticmethod
    def _apply_teacher_profile_rules(
        validated_data: dict,
        request_user: User,
        course: Course | None = None,
    ) -> dict:
        if request_user.role == User.RoleChoices.ADMINISTRATOR:
            return validated_data

        if course is None:
            validated_data["teacher_profile"] = request_user.teacher_profile
        else:
            validated_data.pop("teacher_profile", None)

        return validated_data

    @staticmethod
    @transaction.atomic
    def create_course(validated_data: dict, request_user: User) -> Course:
        validated_data = CourseService._apply_teacher_profile_rules(
            dict(validated_data),
            request_user,
        )
        validated_data = CourseService._apply_slug_rules(validated_data)
        tags = validated_data.pop("tags", [])
        course = Course.all_objects.create(**validated_data)
        if tags:
            course.tags.set(tags)
        return course

    @staticmethod
    @transaction.atomic
    def update_course(
        course: Course,
        validated_data: dict,
        request_user: User,
    ) -> Course:
        validated_data = CourseService._apply_teacher_profile_rules(
            dict(validated_data),
            request_user,
            course=course,
        )
        validated_data = CourseService._apply_slug_rules(
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

    @classmethod
    def get_teacher_courses_queryset(cls, teacher_profile):
        return cls.annotate_min_price(
            teacher_profile.courses
            .select_related("teacher_profile__user", "category")
            .prefetch_related("tags")
        )

    @classmethod
    def get_enrolled_courses_queryset(cls, student_profile):
        from apps.enrollments.models import Enrollment

        active_course_ids = (
            Enrollment.objects.with_active_access()
            .filter(student_profile=student_profile)
            .values_list("course_id", flat=True)
        )
        return cls.annotate_min_price(
            Course.objects.filter(pk__in=active_course_ids)
            .select_related("teacher_profile__user", "category")
            .prefetch_related("tags")
        )

    @classmethod
    def get_new_courses(
        cls,
        limit: int = DEFAULT_NEW_COURSES_LIMIT,
        context: dict | None = None,
    ) -> list[dict]:
        courses = cls.annotate_min_price(
            Course.objects.filter(status=Course.StatusChoices.PUBLISHED)
        ).order_by("-published_at")[:limit]
        return CourseListSerializer(courses, many=True, context=context or {}).data

    @classmethod
    def get_popular_courses(
        cls,
        limit: int = DEFAULT_POPULAR_COURSES_LIMIT,
        context: dict | None = None,
    ) -> list[dict]:
        courses = cls.annotate_min_price(
            Course.objects.filter(status=Course.StatusChoices.PUBLISHED)
        ).order_by("-rating_avg")[:limit]
        return CourseListSerializer(courses, many=True, context=context or {}).data

    @staticmethod
    def get_categories(limit: int = DEFAULT_FEATURED_CATEGORIES_LIMIT) -> list[dict]:
        categories = Category.objects.all()[:limit]
        return CategorySerializer(categories, many=True).data
