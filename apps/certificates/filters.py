import django_filters
from django.db.models import Q

from apps.certificates.models import Certificate


class CertificateFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    status = django_filters.ChoiceFilter(choices=Certificate.StatusChoices.choices)
    course = django_filters.CharFilter(field_name="course__slug")
    issued_from = django_filters.DateFilter(field_name="issued_at", lookup_expr="date__gte")
    issued_to = django_filters.DateFilter(field_name="issued_at", lookup_expr="date__lte")

    class Meta:
        model = Certificate
        fields = ["search", "status", "course", "issued_from", "issued_to"]

    def filter_search(self, queryset, name, value):
        query = value.strip()

        if not query:
            return queryset

        # student_name / course_title are the issue-time snapshots, so a support
        # ticket quoting the name printed on the PDF still finds the row after
        # the student or the course has been renamed.
        return queryset.filter(
            Q(serial__icontains=query)
            | Q(student_name__icontains=query)
            | Q(course_title__icontains=query)
            | Q(student_profile__user__email__icontains=query)
        )
