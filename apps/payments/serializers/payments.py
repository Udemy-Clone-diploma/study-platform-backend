from rest_framework import serializers

from apps.payments.models import Payment, PaymentAttempt

from .items import PaymentItemSerializer
from .orders import OrderSerializer


class PaymentSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()
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

    class Meta:
        model = Payment
        fields = [
            "id",
            "user",
            "user_info",
            "student_profile",
            "order_id",
            "order",
            "installment_id",
            "installment_number",
            "amount",
            "currency",
            "status",
            "payment_method",
            "description",
            "checkout_url",
            "stripe_payment_intent_id",
            "stripe_session_id",
            "stripe_customer_id",
            "metadata",
            "items",
            "is_successful",
            "is_pending",
            "can_be_refunded",
            "created_at",
            "updated_at",
            "processed_at",
        ]
        read_only_fields = fields

    def get_user_info(self, obj: Payment) -> dict:
        return {
            "id": obj.user_id,
            "email": obj.user.email,
            "name": obj.user.get_full_name(),
        }


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
