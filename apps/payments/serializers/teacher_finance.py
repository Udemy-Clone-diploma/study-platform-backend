from decimal import Decimal

from rest_framework import serializers

from apps.payments.models import (
    TeacherLedgerEntry,
    TeacherPayout,
)


class TeacherBalanceSerializer(serializers.Serializer):
    currency = serializers.CharField()
    earned = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    refunded = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    paid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    adjustments = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    reserved = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    balance = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    available = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )


class TeacherLedgerEntrySerializer(
    serializers.ModelSerializer
):
    payment_id = serializers.IntegerField(
        read_only=True
    )
    refund_id = serializers.IntegerField(
        read_only=True
    )
    payout_id = serializers.IntegerField(
        read_only=True
    )

    class Meta:
        model = TeacherLedgerEntry
        fields = [
            "id",
            "entry_type",
            "status",
            "amount",
            "currency",
            "payment_id",
            "refund_id",
            "payout_id",
            "description",
            "posted_at",
            "created_at",
        ]
        read_only_fields = fields


class TeacherPayoutSerializer(
    serializers.ModelSerializer
):
    destination_type = (
        serializers.SerializerMethodField()
    )
    failure_reason = (
        serializers.SerializerMethodField()
    )
    request_uncertain = (
        serializers.SerializerMethodField()
    )
    payout_mode = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = TeacherPayout
        fields = [
            "id",
            "amount",
            "currency",
            "status",
            "provider",
            "provider_status",
            "provider_order_id",
            "provider_payment_id",
            "provider_transaction_id",
            "destination_type",
            "failure_reason",
            "request_uncertain",
            "payout_mode",
            "processed_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_destination_type(
        self,
        obj: TeacherPayout,
    ) -> str:
        snapshot = obj.destination_snapshot or {}

        destination_type = str(
            snapshot.get(
                "destination_type",
                "",
            )
        ).strip()

        if destination_type:
            return destination_type

        if obj.destination_id:
            return str(
                obj.destination.destination_type
            )

        return ""

    def get_failure_reason(
        self,
        obj: TeacherPayout,
    ) -> str:
        return str(
            (obj.metadata or {}).get(
                "failure_reason",
                "",
            )
        )

    def get_request_uncertain(
        self,
        obj: TeacherPayout,
    ) -> bool:
        return bool(
            (obj.metadata or {}).get(
                "request_uncertain",
                False,
            )
        )

    def get_payout_mode(
        self,
        obj: TeacherPayout,
    ) -> str:
        return str(
            (obj.metadata or {}).get(
                "payout_mode",
                "",
            )
        )

class StaffPayoutCreateSerializer(
    serializers.Serializer
):
    teacher_id = serializers.IntegerField(
        min_value=1,
    )

    destination_id = serializers.IntegerField(
        min_value=1,
        required=False,
    )

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    currency = serializers.ChoiceField(
        choices=[
            "UAH",
            "USD",
            "EUR",
        ]
    )

    idempotency_key = serializers.CharField(
        max_length=255,
    )

    def validate_idempotency_key(
        self,
        value,
    ):
        value = str(value).strip()

        if not value:
            raise serializers.ValidationError(
                "Idempotency key is required."
            )

        return value


class StaffTeacherPayoutSerializer(
    TeacherPayoutSerializer
):
    teacher_id = serializers.IntegerField(
        read_only=True
    )

    teacher_email = serializers.EmailField(
        source="teacher.user.email",
        read_only=True,
    )

    created_by_id = serializers.IntegerField(
        read_only=True
    )

    created_by_email = serializers.EmailField(
        source="created_by.email",
        read_only=True,
        allow_null=True,
    )

    class Meta(
        TeacherPayoutSerializer.Meta
    ):
        fields = (
            TeacherPayoutSerializer.Meta.fields
            + [
                "teacher_id",
                "teacher_email",
                "created_by_id",
                "created_by_email",
            ]
        )

        read_only_fields = fields