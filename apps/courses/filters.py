import django_filters
from django.db.models import Q

from apps.common.i18n import SUPPORTED_LOCALES
from apps.courses.models import Category, Course
from apps.users.models import User


class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    pass


class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass


class CategoryFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")

    def filter_search(self, queryset, name, value):
        query = value.strip()

        if not query:
            return queryset

        # Matches whichever locale the admin actually typed the category in.
        condition = Q()
        for locale in SUPPORTED_LOCALES:
            condition |= Q(**{f"name_{locale}__icontains": query})
            condition |= Q(**{f"description_{locale}__icontains": query})
        return queryset.filter(condition)

    class Meta:
        model = Category
        fields = ["search"]


class CourseFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(
        field_name="category__slug",
        lookup_expr="exact",
    )
    mode = CharInFilter(field_name="mode", lookup_expr="in")
    delivery_type = CharInFilter(field_name="delivery_type", lookup_expr="in")
    level = CharInFilter(field_name="level", lookup_expr="in")
    language = CharInFilter(field_name="language", lookup_expr="in")
    course_type = CharInFilter(field_name="course_type", lookup_expr="in")
    format_type = CharInFilter(field_name="delivery_formats__format_type", lookup_expr="in")
    price_min = django_filters.NumberFilter(field_name="min_price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="min_price", lookup_expr="lte")
    with_certificate = django_filters.BooleanFilter(field_name="with_certificate")
    is_on_sale = django_filters.BooleanFilter(field_name="is_on_sale")
    rating_min = django_filters.NumberFilter(field_name="rating_avg", lookup_expr="gte")
    plan_kind = django_filters.CharFilter(method="filter_plan_kind")
    search = django_filters.CharFilter(method="filter_search")
    status = django_filters.CharFilter(method="filter_status")

    def filter_status(self, queryset, name, value):
        # Admin-only status tabs. Ignored (not a 400) for everyone else so the
        # public catalog stays published-only even with a handcrafted ?status=;
        # unknown values are dropped, pending_edit is internal-only.
        user = getattr(self.request, "user", None)
        if (
            user is None
            or not user.is_authenticated
            or user.role != User.RoleChoices.ADMINISTRATOR
        ):
            return queryset
        statuses = [
            item
            for item in (part.strip() for part in value.split(","))
            if item in Course.StatusChoices.values
            and item != Course.StatusChoices.PENDING_EDIT
        ]
        if not statuses:
            return queryset
        return queryset.filter(status__in=statuses)

    def filter_plan_kind(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            delivery_formats__format_type=value,
            delivery_formats__pricing__isnull=False,
        ).distinct()

    def filter_search(self, queryset, name, value):
        query = value.strip()

        if not query:
            return queryset

        # Category name is matched across every locale the admin filled in
        # (apps.common.i18n), since the course's category can be typed in any of them.
        category_condition = Q()
        for locale in SUPPORTED_LOCALES:
            category_condition |= Q(**{f"category__name_{locale}__icontains": query})

        return queryset.filter(
            Q(title__icontains=query)
            | Q(subtitle__icontains=query)
            | Q(short_description__icontains=query)
            | Q(full_description__icontains=query)
            | category_condition
            | Q(tags__name__icontains=query)
            | Q(teacher_profile__user__first_name__icontains=query)
            | Q(teacher_profile__user__last_name__icontains=query)
        ).distinct()

    class Meta:
        model = Course
        fields = [
            "category",
            "mode",
            "delivery_type",
            "level",
            "language",
            "course_type",
            "format_type",
            "price_min",
            "price_max",
            "with_certificate",
            "is_on_sale",
            "rating_min",
            "plan_kind",
            "search",
            "status",
        ]
