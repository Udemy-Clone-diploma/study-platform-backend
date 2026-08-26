from django.db import models


class TeacherPayoutAccount(models.Model):
    class StatusChoices(models.TextChoices):
        INCOMPLETE = "incomplete", "Setup incomplete"
        PENDING = "pending", "Verification pending"
        ACTIVE = "active", "Active"
        RESTRICTED = "restricted", "Restricted"

    teacher = models.OneToOneField(
        "users.TeacherProfile", on_delete=models.CASCADE, related_name="payout_account"
    )
    provider = models.CharField(max_length=20, default="stripe")
    provider_account_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=24, choices=StatusChoices.choices, default=StatusChoices.INCOMPLETE
    )
    details_submitted = models.BooleanField(default=False)
    charges_enabled = models.BooleanField(default=False)
    payouts_enabled = models.BooleanField(default=False)
    country = models.CharField(max_length=2, blank=True, default="")
    outstanding_requirements = models.JSONField(default=list, blank=True)
    disabled_reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "teacher_payout_accounts"

    @property
    def is_active(self):
        return self.details_submitted and self.charges_enabled and self.payouts_enabled
