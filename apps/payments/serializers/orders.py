from rest_framework import serializers

from apps.payments.models import Order

from .installments import PaymentInstallmentSerializer
from .items import OrderItemSerializer


class OrderSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()
    items = OrderItemSerializer(many=True, read_only=True)
    installments = PaymentInstallmentSerializer(many=True, read_only=True)
    paid_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_paid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "user_info",
            "student_profile",
            "total_amount",
            "currency",
            "status",
            "payment_type",
            "installments_count",
            "paid_amount",
            "remaining_amount",
            "metadata",
            "items",
            "installments",
            "is_paid",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = fields

    def get_user_info(self, obj: Order) -> dict:
        return {
            "id": obj.user_id,
            "email": obj.user.email,
            "name": obj.user.get_full_name(),
        }
