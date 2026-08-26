from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from .payment import Payment


class Order(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"
        REFUNDED = "refunded", "Refunded"

    class PaymentTypeChoices(models.TextChoices):
        FULL = "full", "Full payment"
        INSTALLMENTS = "installments", "Installments"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    student_profile = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="orders",
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentTypeChoices.choices,
        default=PaymentTypeChoices.FULL,
    )
    installments_count = models.PositiveSmallIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["student_profile", "status"]),
            models.Index(fields=["payment_type", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Order {self.id} - {self.user.email} - {self.total_amount} {self.currency}"

    @property
    def paid_amount(self) -> Decimal:
        """Total of the succeeded payments. Sums `payments.all()` in Python
        rather than aggregating in the DB so that a caller which prefetched
        them (the list endpoints) spends no query per order. Read-side only:
        `sync_status_from_payments` deliberately does not use this."""
        return sum(
            (
                payment.amount
                for payment in self.payments.all()
                if payment.status == Payment.StatusChoices.SUCCEEDED
            ),
            Decimal("0.00"),
        )

    @property
    def remaining_amount(self) -> Decimal:
        remaining = self.total_amount - self.paid_amount
        return max(remaining, Decimal("0.00"))

    @property
    def is_paid(self) -> bool:
        return self.status == self.StatusChoices.PAID

    def sync_status_from_payments(self) -> None:
        # Aggregates in the DB instead of reusing `paid_amount`: this runs on
        # the payment provider callback path path immediately after a payment row was written,
        # so it has to read committed state and never a `payments` prefetch
        # cache the calling instance might already be holding.
        paid_amount = self.payments.filter(status=Payment.StatusChoices.SUCCEEDED).aggregate(
            total=Sum("amount")
        ).get("total") or Decimal("0.00")
        if paid_amount >= self.total_amount:
            self.status = self.StatusChoices.PAID
            self.completed_at = timezone.now()
        elif paid_amount > Decimal("0.00"):
            self.status = self.StatusChoices.PARTIALLY_PAID
            self.completed_at = None
        else:
            self.status = self.StatusChoices.PENDING
            self.completed_at = None
        self.save(update_fields=["status", "completed_at", "updated_at"])

    def mark_as_canceled(self, reason: str = "") -> None:
        self.status = self.StatusChoices.CANCELED
        if reason:
            self.metadata = {**self.metadata, "cancel_reason": reason}
        self.save(update_fields=["status", "metadata", "updated_at"])


class OrderItem(models.Model):
    order = models.ForeignKey(
        "payments.Order",
        on_delete=models.CASCADE,
        related_name="items",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    pricing_plan = models.ForeignKey(
        "courses.PricingPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    cohort = models.ForeignKey(
        "courses.Cohort",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    schedule_slots = models.ManyToManyField(
        "schedule.ScheduleSlot",
        related_name="order_items",
        blank=True,
    )
    course_title = models.CharField(max_length=255)
    course_slug = models.SlugField()
    pricing_plan_kind = models.CharField(max_length=20, blank=True, default="")
    unit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_items"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "course"],
                name="unique_order_item_per_course",
            )
        ]

    def __str__(self):
        return f"{self.order_id} - {self.course_title} - {self.unit_amount} {self.currency}"
