from django.conf import settings
from django.db import models
from django.utils import timezone


class Refund(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.CASCADE,
        related_name="refunds",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )
    stripe_refund_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_refunds",
    )

    class Meta:
        db_table = "refunds"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Refund {self.id} - Payment {self.payment_id} - {self.amount}"

    @property
    def is_partial(self) -> bool:
        return self.amount < self.payment.amount

    def mark_as_succeeded(self) -> None:
        self.status = self.StatusChoices.SUCCEEDED
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_at"])
