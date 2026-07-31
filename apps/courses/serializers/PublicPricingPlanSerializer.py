from rest_framework import serializers

from apps.courses.models import PricingPlan


class PublicPricingPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingPlan
        fields = [
            "id",
            "price",
            "currency",
            "installment_count",
            "installment_amount",
        ]
        read_only_fields = fields
