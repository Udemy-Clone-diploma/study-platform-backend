import django_filters
from django.db.models import Q

from apps.courses.models import Course


class CourseFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(
        field_name="category__slug",
        lookup_expr="exact",
    )
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
        fields = ["category", "search"]
