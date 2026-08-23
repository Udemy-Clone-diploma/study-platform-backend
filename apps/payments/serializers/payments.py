from decimal import Decimal

from rest_framework import serializers

from apps.common.files import absolute_media_url
from apps.payments.models import Payment, PaymentAttempt, Refund

from .items import PaymentItemSerializer
from .orders import OrderSerializer


class PaymentUserSerializer(serializers.Serializer):
    """The payer, for the admin Finance table."""

    id = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    email = serializers.EmailField(read_only=True)
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, obj) -> str | None:
        return absolute_media_url(obj.avatar, self.context.get("request"))


class PaymentSerializer(serializers.ModelSerializer):
    user = PaymentUserSerializer(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    order = OrderSerializer(read_only=True)
    order_id = serializers.IntegerField(read_only=True)
    installment_id = serializers.IntegerField(read_only=True)
    installment_number = serializers.IntegerField(
        source="installment.installment_number",
        read_only=True,
        allow_null=True,
    )
    items = PaymentItemSerializer(many=True, read_only=True)
    is_successful = serializers.BooleanField(read_only=True)
    is_pending = serializers.BooleanField(read_only=True)
    can_be_refunded = serializers.BooleanField(read_only=True)
    refunded_amount = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "user",
            "user_id",
            "student_profile",
            "order_id",
            "order",
            "installment_id",
            "installment_number",
            "amount",
            "gross_amount",
            "platform_fee_amount",
            "teacher_amount",
            "teacher_id",
            "currency",
            "status",
            "payment_method",
            "description",
            "checkout_url",
            "stripe_payment_intent_id",
            "stripe_session_id",
            "stripe_customer_id",
            "stripe_charge_id",
            "metadata",
            "items",
            "is_successful",
            "is_pending",
            "can_be_refunded",
            "refunded_amount",
            "created_at",
            "updated_at",
            "processed_at",
        ]
        read_only_fields = fields

    def get_refunded_amount(self, obj: Payment) -> str:
        """Total successfully refunded. A partial refund leaves `status` at
        succeeded, so this is the only field that shows it happened."""
        total = sum(
            (
                refund.amount
                for refund in obj.refunds.all()
                if refund.status == Refund.StatusChoices.SUCCEEDED
            ),
            Decimal("0.00"),
        )
        return f"{total:.2f}"


class PaymentAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAttempt
        fields = [
            "id",
            "stripe_charge_id",
            "status",
            "error_message",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
