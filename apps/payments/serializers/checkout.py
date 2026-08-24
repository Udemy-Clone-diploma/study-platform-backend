from rest_framework import serializers

from apps.payments.models import Order, Payment


class CheckoutSessionCreateSerializer(serializers.Serializer):
    success_url = serializers.URLField(required=False)
    cancel_url = serializers.URLField(required=False)
    selected_cart_item_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        required=False,
    )
    payment_type = serializers.ChoiceField(
        choices=Order.PaymentTypeChoices.choices,
        default=Order.PaymentTypeChoices.FULL,
        required=False,
    )
    installments_count = serializers.IntegerField(
        min_value=2,
        max_value=24,
        required=False,
    )


class CheckoutSessionSerializer(serializers.Serializer):
    checkout_url = serializers.URLField(read_only=True)
    session_id = serializers.CharField(read_only=True)
    payment_id = serializers.IntegerField(read_only=True)
    order_id = serializers.IntegerField(read_only=True)
    installment_id = serializers.IntegerField(read_only=True, allow_null=True)


class LiqPayCheckoutCreateSerializer(serializers.Serializer):
    selected_cart_item_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        required=False,
    )
    payment_type = serializers.ChoiceField(
        choices=Order.PaymentTypeChoices.choices,
        default=Order.PaymentTypeChoices.FULL,
        required=False,
    )
    installments_count = serializers.IntegerField(
        min_value=2,
        max_value=24,
        required=False,
    )


class LiqPayCheckoutSerializer(serializers.Serializer):
    checkout_url = serializers.URLField(read_only=True)
    data = serializers.CharField(read_only=True)
    signature = serializers.CharField(read_only=True)
    provider_order_id = serializers.CharField(read_only=True)
    payment_id = serializers.IntegerField(read_only=True)
    order_id = serializers.IntegerField(read_only=True)
    installment_id = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    currency = serializers.CharField(read_only=True)


class LiqPayStatusSyncSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField(
        min_value=1,
    )


class LiqPayStatusSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField(
        read_only=True,
    )
    order_id = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )
    installment_id = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )
    payment_status = serializers.CharField(
        read_only=True,
    )
    provider_status = serializers.CharField(
        read_only=True,
    )


class PaymentIntentCreateSerializer(CheckoutSessionCreateSerializer):
    pass


class PaymentIntentSerializer(serializers.Serializer):
    client_secret = serializers.CharField(read_only=True)
    payment_intent_id = serializers.CharField(read_only=True)
    payment_id = serializers.IntegerField(read_only=True)
    order_id = serializers.IntegerField(read_only=True)
    installment_id = serializers.IntegerField(read_only=True, allow_null=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    currency = serializers.CharField(read_only=True)


class PaymentIntentStatusSyncSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField(min_value=1)
    payment_intent_id = serializers.CharField(max_length=255)


class PaymentIntentStatusSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField(read_only=True)
    order_id = serializers.IntegerField(read_only=True, allow_null=True)
    installment_id = serializers.IntegerField(read_only=True, allow_null=True)
    payment_status = serializers.ChoiceField(
        choices=Payment.StatusChoices.choices,
        read_only=True,
    )
    order_status = serializers.ChoiceField(
        choices=Order.StatusChoices.choices,
        read_only=True,
        allow_null=True,
    )
    stripe_payment_intent_status = serializers.CharField(read_only=True)
