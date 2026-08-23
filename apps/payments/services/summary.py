from datetime import date, timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.fields import DateField
from django.db.models.functions import (
    Coalesce,
    NullIf,
    TruncDate,
    TruncMonth,
    TruncWeek,
)

from apps.payments.models import Payment, PaymentItem, Refund

from .base import PaymentBaseService
from .exceptions import PaymentError

ZERO = Decimal("0.00")
MONEY = DecimalField(max_digits=14, decimal_places=2)
TRUNC_FUNCTIONS = {
    "day": TruncDate,
    "week": TruncWeek,
    "month": TruncMonth,
}
# What was actually charged, before refunds. A fully refunded payment keeps its
# charge here and reports the reversal through `refunded_amount` instead: taking
# the charge out of revenue *and* subtracting the refund would count the reversal
# twice and drive `net_revenue` negative on a single refunded payment.
CHARGED_STATUSES = [
    Payment.StatusChoices.SUCCEEDED,
    Payment.StatusChoices.REFUNDED,
]


class SummaryService(PaymentBaseService):
    @staticmethod
    def _one_row_per_payment(queryset):
        """The `search`, `course` and `teacher` filters join `items` (and
        `has_refund` joins `refunds`), which fans a payment out into one row per
        matching child. Re-selecting by pk collapses that back to one row each,
        so a two-course payment is not summed twice."""
        return Payment.objects.filter(pk__in=queryset.values("pk"))

    @staticmethod
    def _sum_where(condition: Q):
        return Coalesce(Sum("amount", filter=condition), ZERO, output_field=MONEY)

    @staticmethod
    def _refunded_by_currency(payments) -> dict[str, Decimal]:
        """Money actually returned, read from the `Refund` rows rather than from
        `Payment.status`. A partial refund leaves the payment `succeeded`, so
        status alone cannot see it. Kept as its own query because joining refunds
        into the grouped query above would fan a twice-refunded payment out into
        two rows and double its charge."""
        rows = (
            Refund.objects.filter(
                payment__in=payments,
                status=Refund.StatusChoices.SUCCEEDED,
            )
            .values("payment__currency")
            .annotate(total=Sum("amount", output_field=MONEY))
        )
        return {row["payment__currency"]: row["total"] for row in rows}

    @classmethod
    def payment_summary(cls, queryset) -> dict:
        """Stat-tile totals over a filtered payment queryset: one grouped query
        for the money charged, one for what came back, two for the counts."""
        payments = cls._one_row_per_payment(queryset)
        statuses = Payment.StatusChoices
        refunded_by_currency = cls._refunded_by_currency(
            payments.filter(status__in=CHARGED_STATUSES)
        )

        rows = (
            payments.values("currency")
            .annotate(
                gross_revenue=cls._sum_where(Q(status__in=CHARGED_STATUSES)),
                pending_amount=cls._sum_where(
                    Q(status__in=[statuses.PENDING, statuses.PROCESSING])
                ),
            )
            .order_by("currency")
        )
        by_currency = []
        for row in rows:
            refunded = refunded_by_currency.get(row["currency"], ZERO)
            by_currency.append(
                {
                    **row,
                    "refunded_amount": refunded,
                    "net_revenue": row["gross_revenue"] - refunded,
                }
            )

        counts = payments.aggregate(
            total=Count("id"),
            **{value: Count("id", filter=Q(status=value)) for value in statuses.values},
        )
        # Separate query: the join to refunds would multiply the rows the counts
        # above are taken over. A partly refunded payment is still `succeeded`,
        # so without this the admin has no way to see that it happened.
        counts["partially_refunded"] = (
            payments.filter(refunds__status=Refund.StatusChoices.SUCCEEDED)
            .exclude(status=statuses.REFUNDED)
            .distinct()
            .count()
        )
        return {"by_currency": by_currency, "counts": counts}

    @classmethod
    def payment_timeseries(
        cls,
        queryset,
        group_by: str,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict]:
        """Gross revenue per period per currency, for the revenue chart.

        Zero-filled: a period with no revenue comes back as "0.00" rather than
        being skipped, so the chart cannot compress a quiet stretch into a
        straight line between two distant points and misreport the trend.
        """
        trunc = TRUNC_FUNCTIONS.get(group_by)
        if trunc is None:
            raise PaymentError(
                f"Unsupported group_by '{group_by}'. Use one of: "
                f"{', '.join(TRUNC_FUNCTIONS)}."
            )

        payments = cls._one_row_per_payment(queryset).filter(status__in=CHARGED_STATUSES)
        rows = list(
            payments
            # DateField output keeps week/month buckets as dates rather than
            # midnight datetimes, which the response serializer refuses.
            .annotate(period=trunc("created_at", output_field=DateField()))
            .values("period", "currency")
            .annotate(gross_revenue=Sum("amount", output_field=MONEY))
            .order_by("period", "currency")
        )
        return cls._zero_fill(rows, group_by, date_from, date_to)

    @classmethod
    def _zero_fill(
        cls, rows: list[dict], group_by: str, date_from: date | None, date_to: date | None,
    ) -> list[dict]:
        """Span the requested window, or the observed data when no window was
        given. Every currency gets its own continuous series, so a currency that
        only traded in one month still plots as a flat line either side."""
        if not rows and not (date_from and date_to):
            return []

        periods = [row["period"] for row in rows]
        start = date_from or min(periods)
        end = date_to or max(periods)
        if start > end:
            return []

        currencies = sorted({row["currency"] for row in rows})
        known = {(row["period"], row["currency"]): row["gross_revenue"] for row in rows}
        return [
            {
                "period": bucket,
                "currency": currency,
                "gross_revenue": known.get((bucket, currency), ZERO),
            }
            for bucket in cls._buckets(group_by, start, end)
            for currency in currencies
        ]

    @classmethod
    def _buckets(cls, group_by: str, start: date, end: date) -> list[date]:
        """Bucket start dates, aligned the same way the DB truncation aligns
        them: Monday for weeks, the 1st for months."""
        if group_by == "week":
            current = start - timedelta(days=start.weekday())
        elif group_by == "month":
            current = start.replace(day=1)
        else:
            current = start

        buckets = []
        while current <= end:
            buckets.append(current)
            if group_by == "month":
                current = cls._add_months(current, 1)
            else:
                current += timedelta(days=7 if group_by == "week" else 1)
        return buckets

    @staticmethod
    def previous_window(date_from: date, date_to: date) -> tuple[date, date]:
        """The equally long window ending the day before `date_from`."""
        length = (date_to - date_from).days + 1
        previous_to = date_from - timedelta(days=1)
        return previous_to - timedelta(days=length - 1), previous_to

    @classmethod
    def revenue_by_category(cls, queryset) -> list[dict]:
        """Gross revenue split by course category, for the donut.

        Aggregated per payment item, because one payment can carry courses from
        different categories. Each payment's amount is split across its items in
        proportion to their unit prices rather than summing `unit_amount`
        directly: an installment payment snapshots the *full* order item price,
        so summing those would bill a 3-installment course three times over.
        The split makes each currency's categories add back up to the
        `gross_revenue` that /payments/summary/ reports, so it spans the same
        charged statuses that tile does.
        """
        payments = cls._one_row_per_payment(queryset).filter(status__in=CHARGED_STATUSES)
        items_total = (
            PaymentItem.objects.filter(payment_id=OuterRef("payment_id"))
            .values("payment_id")
            .annotate(total=Sum("unit_amount"))
            .values("total")[:1]
        )
        rows = (
            PaymentItem.objects.filter(payment__in=payments)
            .annotate(items_total=Subquery(items_total, output_field=MONEY))
            .annotate(
                attributed=ExpressionWrapper(
                    F("payment__amount")
                    * F("unit_amount")
                    # NullIf keeps a fully discounted (zero-priced) payment from
                    # dividing by zero; those rows drop out instead of erroring.
                    / NullIf(F("items_total"), Value(Decimal("0.00"))),
                    output_field=MONEY,
                )
            )
            .values(
                "course__category_id",
                "course__category__name_en",
                "course__category__slug",
                "payment__currency",
            )
            .annotate(gross_revenue=Sum("attributed", output_field=MONEY))
            .order_by("payment__currency", "-gross_revenue")
        )
        results = {
            (row["payment__currency"], row["course__category_id"]): {
                # Null when the course was hard-deleted or has no category. The
                # bucket is kept rather than dropped so the donut still adds up.
                "category_id": row["course__category_id"],
                "category": row["course__category__name_en"],
                "slug": row["course__category__slug"],
                "currency": row["payment__currency"],
                "gross_revenue": row["gross_revenue"] or ZERO,
            }
            for row in rows
        }

        # A payment carrying no items at all (recorded by hand in the admin
        # rather than through checkout) has nothing to join a category to. Its
        # revenue folds into the same uncategorized bucket, because dropping it
        # would leave the donut short of the gross_revenue tile.
        itemless = (
            payments.filter(items__isnull=True)
            .values("currency")
            .annotate(total=Sum("amount", output_field=MONEY))
        )
        for row in itemless:
            bucket = results.setdefault(
                (row["currency"], None),
                {
                    "category_id": None,
                    "category": None,
                    "slug": None,
                    "currency": row["currency"],
                    "gross_revenue": ZERO,
                },
            )
            bucket["gross_revenue"] += row["total"]

        return sorted(
            results.values(), key=lambda row: (row["currency"], -row["gross_revenue"])
        )
