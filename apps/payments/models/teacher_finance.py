from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TeacherPayout(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    class ProviderChoices(models.TextChoices):
        LIQPAY = "liqpay", "LiqPay"
        MANUAL = "manual", "Manual"

    teacher = models.ForeignKey(
        "users.TeacherProfile",
        on_delete=models.PROTECT,
        related_name="payouts",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
    )

    destination = models.ForeignKey(
        "payments.TeacherPayoutDestination",
        on_delete=models.PROTECT,
        related_name="payouts",
        null=True,
        blank=True,
    )

    destination_snapshot = models.JSONField(
        default=dict,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )

    provider = models.CharField(
        max_length=20,
        choices=ProviderChoices.choices,
        default=ProviderChoices.LIQPAY,
    )

    provider_order_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    provider_payment_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    provider_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    provider_status = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_teacher_payouts",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "teacher_payouts"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=Decimal("0.00")),
                name="teacher_payout_amount_positive",
            ),
            models.UniqueConstraint(
                fields=[
                    "provider",
                    "provider_order_id",
                ],
                condition=~Q(provider_order_id=""),
                name="unique_teacher_payout_provider_order",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "teacher",
                    "currency",
                    "status",
                ],
                name="teacher_payout_balance_idx",
            ),
            models.Index(
                fields=[
                    "provider",
                    "provider_status",
                ],
                name="teacher_payout_provider_idx",
            ),
            models.Index(
                fields=["created_at"],
                name="teacher_payout_created_idx",
            ),
        ]

    def __str__(self):
        return f"Teacher payout {self.id}: {self.amount} {self.currency}"

    def mark_as_processing(
        self,
        *,
        provider_status: str = "",
    ) -> None:
        self.status = self.StatusChoices.PROCESSING
        self.provider_status = provider_status

        self.save(
            update_fields=[
                "status",
                "provider_status",
                "updated_at",
            ]
        )

    def mark_as_succeeded(
        self,
        *,
        provider_status: str = "",
        provider_payment_id: str = "",
        provider_transaction_id: str = "",
    ) -> None:
        self.status = self.StatusChoices.SUCCEEDED
        self.provider_status = provider_status
        self.processed_at = timezone.now()

        update_fields = [
            "status",
            "provider_status",
            "processed_at",
            "updated_at",
        ]

        if provider_payment_id:
            self.provider_payment_id = provider_payment_id
            update_fields.append("provider_payment_id")

        if provider_transaction_id:
            self.provider_transaction_id = provider_transaction_id
            update_fields.append("provider_transaction_id")

        self.save(update_fields=update_fields)

    def mark_as_failed(
        self,
        *,
        provider_status: str = "",
        reason: str = "",
    ) -> None:
        self.status = self.StatusChoices.FAILED
        self.provider_status = provider_status
        self.processed_at = timezone.now()

        if reason:
            self.metadata = {
                **(self.metadata or {}),
                "failure_reason": reason,
            }

        self.save(
            update_fields=[
                "status",
                "provider_status",
                "processed_at",
                "metadata",
                "updated_at",
            ]
        )


class TeacherLedgerEntry(models.Model):
    class TypeChoices(models.TextChoices):
        EARNING = "earning", "Earning"
        REFUND = "refund", "Refund adjustment"
        PAYOUT = "payout", "Payout"
        ADJUSTMENT = "adjustment", "Manual adjustment"

    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        POSTED = "posted", "Posted"
        VOID = "void", "Void"

    teacher = models.ForeignKey(
        "users.TeacherProfile",
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )

    entry_type = models.CharField(
        max_length=20,
        choices=TypeChoices.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
    )

    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_ledger_entries",
    )

    refund = models.ForeignKey(
        "payments.Refund",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_ledger_entries",
    )

    payout = models.ForeignKey(
        "payments.TeacherPayout",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )

    source_key = models.CharField(
        max_length=255,
        unique=True,
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    posted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "teacher_ledger_entries"
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(amount=Decimal("0.00")),
                name="teacher_ledger_amount_nonzero",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "teacher",
                    "currency",
                    "status",
                ],
                name="teacher_ledger_balance_idx",
            ),
            models.Index(
                fields=[
                    "entry_type",
                    "status",
                ],
                name="teacher_ledger_type_idx",
            ),
            models.Index(
                fields=["created_at"],
                name="teacher_ledger_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.teacher_id} {self.entry_type}: {self.amount} {self.currency}"

    def post(self) -> None:
        if self.status == self.StatusChoices.POSTED:
            return

        self.status = self.StatusChoices.POSTED
        self.posted_at = timezone.now()

        self.save(
            update_fields=[
                "status",
                "posted_at",
                "updated_at",
            ]
        )

    def void(self) -> None:
        if self.status == self.StatusChoices.VOID:
            return

        self.status = self.StatusChoices.VOID

        self.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )


class TeacherPayoutItem(models.Model):
    payout = models.ForeignKey(
        TeacherPayout,
        on_delete=models.CASCADE,
        related_name="items",
    )

    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="teacher_payout_items",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "teacher_payout_items"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=Decimal("0.00")),
                name="teacher_payout_item_amount_positive",
            ),
            models.UniqueConstraint(
                fields=[
                    "payout",
                    "payment",
                ],
                name="unique_payment_per_teacher_payout",
            ),
        ]

    def __str__(self):
        return f"Payout {self.payout_id} / payment {self.payment_id}: {self.amount} {self.currency}"
