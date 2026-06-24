from django.db import models


class PricingPlan(models.Model):
    class CurrencyChoices(models.TextChoices):
        USD = "USD", "USD"
        EUR = "EUR", "EUR"
        UAH = "UAH", "UAH"

    delivery_format = models.OneToOneField(
        "courses.CourseDeliveryFormat",
        on_delete=models.CASCADE,
        related_name="pricing",
    )
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

    def __str__(self):
        return f"{self.delivery_format} – {self.price} {self.currency}"
