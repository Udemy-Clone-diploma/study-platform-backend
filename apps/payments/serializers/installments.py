from rest_framework import serializers

from apps.payments.models import PaymentInstallment


class PaymentInstallmentSerializer(serializers.ModelSerializer):
    is_paid = serializers.BooleanField(read_only=True)
    can_start_payment = serializers.BooleanField(read_only=True)

    class Meta:
        model = PaymentInstallment
        fields = [
            "id",
            "installment_number",
            "amount",
            "currency",
            "due_date",
            "status",
            "paid_at",
            "is_paid",
            "can_start_payment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
