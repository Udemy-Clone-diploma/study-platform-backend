from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Payment(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"
        REFUNDED = "refunded", "Refunded"

    class MethodChoices(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        LIQPAY = "liqpay", "LiqPay"
        MANUAL = "manual", "Manual"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    student_profile = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    order = models.ForeignKey(
        "payments.Order",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="payments",
    )
    installment = models.ForeignKey(
        "payments.PaymentInstallment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    teacher = models.ForeignKey(
        "users.TeacherProfile", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="course_payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    platform_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    teacher_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=MethodChoices.choices,
        default=MethodChoices.STRIPE,
    )
    description = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    checkout_url = models.TextField(blank=True, default="")
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, default="")
    stripe_session_id = models.CharField(max_length=255, blank=True, default="")
    stripe_customer_id = models.CharField(max_length=255, blank=True, default="")
    stripe_charge_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["student_profile", "status"]),
            models.Index(fields=["order", "status"]),
            models.Index(fields=["installment", "status"]),
            models.Index(fields=["stripe_payment_intent_id"]),
            models.Index(fields=["stripe_session_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Payment {self.id} - {self.user.email} - {self.amount} {self.currency}"

    @property
    def is_successful(self) -> bool:
        return self.status == self.StatusChoices.SUCCEEDED

    @property
    def is_pending(self) -> bool:
        return self.status in {
            self.StatusChoices.PENDING,
            self.StatusChoices.PROCESSING,
        }

    @property
    def can_be_refunded(self) -> bool:
        return self.status == self.StatusChoices.SUCCEEDED and self.amount > Decimal("0.00")

    def mark_as_processing(
        self,
        *,
        checkout_url: str = "",
        session_id: str = "",
    ) -> None:
        self.status = self.StatusChoices.PROCESSING
        self.checkout_url = checkout_url

        update_fields = [
            "status",
            "checkout_url",
            "updated_at",
        ]

        if session_id:
            self.stripe_session_id = session_id
            update_fields.append("stripe_session_id")

        self.save(update_fields=update_fields)

    def mark_intent_as_processing(self, *, payment_intent_id: str) -> None:
        self.status = self.StatusChoices.PROCESSING
        self.stripe_payment_intent_id = payment_intent_id
        self.checkout_url = ""
        self.save(
            update_fields=[
                "status",
                "stripe_payment_intent_id",
                "checkout_url",
                "updated_at",
            ]
        )

    def mark_as_succeeded(
        self,
        *,
        payment_intent_id: str = "",
        customer_id: str = "",
    ) -> None:
        self.status = self.StatusChoices.SUCCEEDED
        self.processed_at = timezone.now()
        update_fields = [
            "status",
            "processed_at",
            "updated_at",
        ]
        if payment_intent_id:
            self.stripe_payment_intent_id = payment_intent_id
            update_fields.append("stripe_payment_intent_id")
        if customer_id:
            self.stripe_customer_id = customer_id
            update_fields.append("stripe_customer_id")
        self.save(update_fields=update_fields)

    def mark_as_failed(self, reason: str = "") -> None:
        self.status = self.StatusChoices.FAILED
        self.processed_at = timezone.now()
        if reason:
            self.metadata = {**self.metadata, "failure_reason": reason}
        self.save(update_fields=["status", "processed_at", "metadata", "updated_at"])

    def mark_as_canceled(self, reason: str = "") -> None:
        self.status = self.StatusChoices.CANCELED
        self.processed_at = timezone.now()
        if reason:
            self.metadata = {**self.metadata, "cancel_reason": reason}
        self.save(update_fields=["status", "processed_at", "metadata", "updated_at"])


class PaymentItem(models.Model):
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.CASCADE,
        related_name="items",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_items",
    )
    pricing_plan = models.ForeignKey(
        "courses.PricingPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_items",
    )
    cohort = models.ForeignKey(
        "courses.Cohort",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_items",
    )
    schedule_slots = models.ManyToManyField(
        "schedule.ScheduleSlot",
        related_name="payment_items",
        blank=True,
    )
    course_title = models.CharField(max_length=255)
    course_slug = models.SlugField()
    pricing_plan_kind = models.CharField(max_length=20, blank=True, default="")
    unit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_items"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "course"],
                name="unique_payment_item_per_course",
            )
        ]

    def __str__(self):
        return f"{self.payment_id} - {self.course_title} - {self.unit_amount} {self.currency}"


class PaymentAttempt(models.Model):
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.CASCADE,
        related_name="attempts",
    )

    provider = models.CharField(
        max_length=20,
        choices=Payment.MethodChoices.choices,
        default=Payment.MethodChoices.STRIPE,
    )

    # Merchant-side identifier sent to the payment provider.
    # For LiqPay this will be the `order_id` we generate before checkout.
    provider_order_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    # Provider-side payment identifier.
    # LiqPay: `payment_id`.
    provider_payment_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    # Optional provider transaction identifier.
    provider_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    # Exact status received from the provider.
    # Do not collapse LiqPay statuses into our Payment.StatusChoices here.
    provider_status = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    # Legacy Stripe field. Keep until Stripe history has been fully migrated.
    stripe_charge_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=20,
        choices=Payment.StatusChoices.choices,
        default=Payment.StatusChoices.PENDING,
    )

    error_message = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payment_attempts"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_order_id"],
                condition=~Q(provider_order_id=""),
                name="unique_payment_attempt_provider_order_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["provider", "provider_payment_id"],
                name="pay_attempt_provider_id_idx",
            ),
            models.Index(
                fields=["payment", "status"],
                name="pay_attempt_payment_status_idx",
            ),
        ]

    def __str__(self):
        return (
            f"PaymentAttempt {self.id} - "
            f"Payment {self.payment_id} - "
            f"{self.provider} - {self.status}"
        )