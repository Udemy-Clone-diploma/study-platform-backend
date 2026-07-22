import django_filters
from django.db.models import Q, Value
from django.db.models.functions import Concat

from apps.payments.models import Payment, Refund

# Postgres int4 ceiling. A longer digit string in ?search= would blow up the
# order_id comparison instead of simply not matching anything.
MAX_ORDER_ID = 2_147_483_647


class StatusInFilter(django_filters.BaseInFilter, django_filters.ChoiceFilter):
    pass


class PaymentFilter(django_filters.FilterSet):
    """Query surface for the admin Finance panel.

    `/payments/summary/` and `/payments/summary/timeseries/` run the same
    FilterSet, so the stat tiles and the chart always describe the same slice
    the table is showing.
    """

    search = django_filters.CharFilter(method="filter_search")
    status = StatusInFilter(
        field_name="status",
        lookup_expr="in",
        choices=Payment.StatusChoices.choices,
    )
    payment_method = django_filters.ChoiceFilter(choices=Payment.MethodChoices.choices)
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    # The denormalized item columns, not the FK join: PaymentItem.course is
    # SET_NULL, so a deleted course would drop its historic payments out of the
    # finance registry.
    course = django_filters.CharFilter(field_name="items__course_slug", distinct=True)
    user = django_filters.NumberFilter(field_name="user_id")
    teacher = django_filters.NumberFilter(
        field_name="items__course__teacher_profile__user_id",
        distinct=True,
    )
    has_refund = django_filters.BooleanFilter(method="filter_has_refund")

    class Meta:
        model = Payment
        fields = [
            "search",
            "status",
            "payment_method",
            "date_from",
            "date_to",
            "course",
            "user",
            "teacher",
            "has_refund",
        ]

    def filter_has_refund(self, queryset, name, value):
        """Payments carrying money that went back, partial or full. `status` on
        its own cannot express this: a partial refund leaves the payment
        `succeeded`, so nothing in the status list matches it."""
        refunded = Q(refunds__status=Refund.StatusChoices.SUCCEEDED)
        if value:
            return queryset.filter(refunded).distinct()
        return queryset.exclude(refunded)

    def filter_search(self, queryset, name, value):
        query = value.strip()

        if not query:
            return queryset

        matches = (
            Q(payer_full_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(items__course_title__icontains=query)
            | Q(stripe_payment_intent_id__icontains=query)
        )
        if query.isdigit() and int(query) <= MAX_ORDER_ID:
            matches |= Q(order_id=int(query))

        return (
            queryset.annotate(
                payer_full_name=Concat("user__first_name", Value(" "), "user__last_name")
            )
            .filter(matches)
            .distinct()
        )
