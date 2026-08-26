from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from apps.payments.models import Refund


class RefundCreateSerializer(serializers.Serializer):
    """Body of POST /payments/<id>/refund/. Omitting `amount` refunds whatever
    is still refundable on the payment."""

    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class RefundSerializer(serializers.ModelSerializer):
    payment_info = serializers.SerializerMethodField()
    created_by_info = serializers.SerializerMethodField()
    is_partial = serializers.BooleanField(read_only=True)

    class Meta:
        model = Refund
        fields = [
            "id",
            "payment",
            "payment_info",
            "amount",
            "reason",
            "status",
            "is_partial",
            "created_by",
            "created_by_info",
            "stripe_refund_id",
            "created_at",
            "processed_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_by",
            "stripe_refund_id",
            "created_at",
            "processed_at",
        ]

    def get_payment_info(self, obj: Refund) -> dict:
        return {
            "id": obj.payment_id,
            "amount": obj.payment.amount,
            "currency": obj.payment.currency,
            "status": obj.payment.status,
            "user": obj.payment.user.email,
        }

    def get_created_by_info(self, obj: Refund) -> dict | None:
        if obj.created_by is None:
            return None
        return {
            "id": obj.created_by_id,
            "email": obj.created_by.email,
        }

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be positive.")
        return value

    def validate(self, attrs):
        payment = attrs.get("payment")
        if payment is None:
            return attrs

        if not payment.can_be_refunded:
            raise serializers.ValidationError("This payment cannot be refunded.")

        total_refunded = payment.refunds.filter(status=Refund.StatusChoices.SUCCEEDED).aggregate(
            total=Sum("amount")
        ).get("total") or Decimal("0.00")
        if attrs["amount"] > payment.amount - total_refunded:
            raise serializers.ValidationError("Refund amount exceeds remaining payment amount.")
        return attrs
