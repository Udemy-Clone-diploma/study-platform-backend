import django_filters
from django.db.models import Q

from apps.courses.models import Course


class CharInFilter(django_filters.BaseInFilter, django_filters.CharFilter):
    pass


class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass


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
    pricing_type = CharInFilter(field_name="pricing_type", lookup_expr="in")
    with_certificate = django_filters.BooleanFilter(field_name="with_certificate")
    is_on_sale = django_filters.BooleanFilter(field_name="is_on_sale")
    rating_min = django_filters.NumberFilter(field_name="rating_avg", lookup_expr="gte")
    search = django_filters.CharFilter(method="filter_search")

    def filter_search(self, queryset, name, value):
        query = value.strip()

        if not query:
            return queryset

        return queryset.filter(
            Q(title__icontains=query)
            | Q(short_description__icontains=query)
            | Q(full_description__icontains=query)
            | Q(category__name__icontains=query)
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
            "pricing_type",
            "with_certificate",
            "is_on_sale",
            "rating_min",
            "search",
        ]
