import django_filters
from django.db.models import Q

from apps.users.models import User


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
