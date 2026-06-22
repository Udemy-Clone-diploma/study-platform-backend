from rest_framework import serializers

from apps.payments.models import OrderItem, PaymentItem


class PaymentItemSerializer(serializers.ModelSerializer):
    course_id = serializers.IntegerField(read_only=True)
    pricing_plan_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = PaymentItem
        fields = [
            "id",
            "course_id",
            "pricing_plan_id",
            "course_title",
            "course_slug",
            "pricing_plan_kind",
            "unit_amount",
            "currency",
            "created_at",
        ]


class OrderItemSerializer(serializers.ModelSerializer):
    course_id = serializers.IntegerField(read_only=True)
    pricing_plan_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "course_id",
            "pricing_plan_id",
            "course_title",
            "course_slug",
            "pricing_plan_kind",
            "unit_amount",
            "currency",
            "created_at",
        ]
        read_only_fields = fields
