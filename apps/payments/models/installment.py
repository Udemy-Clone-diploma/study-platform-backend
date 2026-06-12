from django.db import models
from django.utils import timezone


class PaymentInstallment(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    order = models.ForeignKey(
        "payments.Order",
        on_delete=models.CASCADE,
        related_name="installments",
    )
    installment_number = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    due_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_installments"
        ordering = ["due_date", "installment_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "installment_number"],
                name="unique_installment_number_per_order",
            )
        ]
        indexes = [
            models.Index(fields=["order", "status"]),
            models.Index(fields=["due_date", "status"]),
        ]

    def __str__(self):
        return f"Order {self.order_id} installment {self.installment_number}"

    @property
    def is_paid(self) -> bool:
        return self.status == self.StatusChoices.PAID

    @property
    def can_start_payment(self) -> bool:
        return self.status in {
            self.StatusChoices.PENDING,
            self.StatusChoices.FAILED,
            self.StatusChoices.PROCESSING,
        }

    def mark_as_processing(self) -> None:
        self.status = self.StatusChoices.PROCESSING
        self.save(update_fields=["status", "updated_at"])

    def mark_as_paid(self) -> None:
        self.status = self.StatusChoices.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at", "updated_at"])

    def mark_as_pending(self) -> None:
        self.status = self.StatusChoices.PENDING
        self.save(update_fields=["status", "updated_at"])

    def mark_as_failed(self) -> None:
        self.status = self.StatusChoices.FAILED
        self.save(update_fields=["status", "updated_at"])
