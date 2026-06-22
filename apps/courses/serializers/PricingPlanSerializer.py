from rest_framework import serializers

from apps.courses.models import PricingPlan


class PricingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingPlan
        fields = [
            "id",
            "price",
            "currency",
            "installment_count",
            "installment_amount",
        ]
