from django.db import models

from .Course import Course


class PricingPlan(models.Model):
    class KindChoices(models.TextChoices):
        GROUP = "group", "Group"
        INDIVIDUAL = "individual", "Individual"

    class CurrencyChoices(models.TextChoices):
        USD = "USD", "USD"
        EUR = "EUR", "EUR"
        UAH = "UAH", "UAH"

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="pricing_plans",
    )
    kind = models.CharField(max_length=20, choices=KindChoices.choices)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        choices=CurrencyChoices.choices,
        default=CurrencyChoices.USD,
    )
    installment_count = models.PositiveSmallIntegerField(null=True, blank=True)
    installment_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )

    class Meta:
        db_table = "pricing_plans"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "kind"], name="unique_pricing_plan_per_kind",
            ),
        ]

    def __str__(self):
        return f"{self.course.title} - {self.kind}"
