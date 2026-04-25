import django_filters

from apps.courses.models import Course


class CourseFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(
        field_name="category__slug",
        lookup_expr="exact",
    )

    class Meta:
        model = Course
        fields = ["category"]
