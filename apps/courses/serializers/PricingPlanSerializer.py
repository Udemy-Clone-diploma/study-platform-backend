from rest_framework import serializers

from apps.courses.models import PricingPlan


class PricingPlanSerializer(serializers.ModelSerializer):
    final_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    final_installment_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, allow_null=True,
    )

    class Meta:
        model = PricingPlan
        fields = [
            "id",
            "price",
            "final_price",
            "currency",
            "installment_count",
            "installment_amount",
            "final_installment_amount",
        ]
