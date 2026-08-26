import django_filters
from django.db.models import Q

from apps.users.models import TeacherApplication, User, UserReport


class UserFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")

    def filter_search(self, queryset, name, value):
        query = value.strip()

        if not query:
            return queryset

        return queryset.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )

    class Meta:
        model = User
        fields = ["role", "status", "is_blocked", "is_deleted", "search"]


class TeacherApplicationFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")

    def filter_search(self, queryset, name, value):
        query = value.strip()

        if not query:
            return queryset

        return queryset.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )

    class Meta:
        model = TeacherApplication
        fields = ["status", "search"]


class UserReportFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=UserReport.StatusChoices.choices)
    resolution = django_filters.ChoiceFilter(choices=UserReport.ResolutionChoices.choices)
    reason = django_filters.ChoiceFilter(choices=UserReport.ReasonChoices.choices)
    search = django_filters.CharFilter(method="filter_search")

    def filter_search(self, queryset, name, value):
        query = value.strip()
        if not query:
            return queryset
        return queryset.filter(
            Q(reporter__first_name__icontains=query)
            | Q(reporter__last_name__icontains=query)
            | Q(reporter__email__icontains=query)
            | Q(reported_user__first_name__icontains=query)
            | Q(reported_user__last_name__icontains=query)
            | Q(reported_user__email__icontains=query)
            | Q(details__icontains=query)
        )

    class Meta:
        model = UserReport
        fields = ["status", "resolution", "reason", "search"]
