from django.db import models


class TeacherPayoutDestination(models.Model):
    class TypeChoices(models.TextChoices):
        BANK_ACCOUNT = (
            "bank_account",
            "Bank account",
        )
        CARD_TOKEN = (
            "card_token",
            "Card token",
        )

    teacher = models.ForeignKey(
        "users.TeacherProfile",
        on_delete=models.CASCADE,
        related_name="payout_destinations",
    )

    provider = models.CharField(
        max_length=20,
        default="liqpay",
    )

    destination_type = models.CharField(
        max_length=30,
        choices=TypeChoices.choices,
    )

    # Bank-account destination.
    receiver_account = models.CharField(
        max_length=64,
        blank=True,
        default="",
    )

    receiver_mfo = models.CharField(
        max_length=16,
        blank=True,
        default="",
    )

    receiver_okpo = models.CharField(
        max_length=32,
        blank=True,
        default="",
    )

    receiver_company = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    # LiqPay token only. NEVER raw PAN/CVV.
    receiver_card_token = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    is_default = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "teacher_payout_destinations"
        ordering = ["-is_default", "-created_at"]
        indexes = [
            models.Index(
                fields=[
                    "teacher",
                    "provider",
                    "is_active",
                ],
                name="teacher_payout_dest_idx",
            ),
        ]

    def __str__(self):
        return f"Teacher {self.teacher_id} {self.destination_type}"
