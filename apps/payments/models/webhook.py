from django.db import models
from django.utils import timezone


class WebhookEvent(models.Model):
    class ProviderChoices(models.TextChoices):
        STRIPE = "stripe", "Stripe"

    class StatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"
        IGNORED = "ignored", "Ignored"

    provider = models.CharField(max_length=20, choices=ProviderChoices.choices)
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )
    data = models.JSONField()
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webhook_events"
        ordering = ["-created_at"]

    def __str__(self):
        return f"WebhookEvent {self.provider} - {self.event_type} - {self.status}"

    def mark_as_processed(self) -> None:
        self.status = self.StatusChoices.PROCESSED
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_at"])

    def mark_as_ignored(self) -> None:
        self.status = self.StatusChoices.IGNORED
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_at"])

    def mark_as_failed(self, error_message: str) -> None:
        self.status = self.StatusChoices.FAILED
        self.error_message = error_message
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "error_message", "processed_at"])
