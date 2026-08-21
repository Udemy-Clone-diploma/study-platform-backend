from django.db import transaction
from rest_framework import serializers

from apps.payments.models import (
    TeacherPayoutDestination,
)


class TeacherPayoutDestinationSerializer(
    serializers.ModelSerializer
):
    receiver_account_masked = (
        serializers.SerializerMethodField()
    )

    has_card_token = (
        serializers.SerializerMethodField()
    )

    # Input only.
    receiver_account = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    receiver_mfo = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    receiver_okpo = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    receiver_company = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    receiver_card_token = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )

    class Meta:
        model = TeacherPayoutDestination

        fields = [
            "id",
            "provider",
            "destination_type",

            "receiver_account",
            "receiver_mfo",
            "receiver_okpo",
            "receiver_company",
            "receiver_card_token",

            "receiver_account_masked",
            "has_card_token",

            "is_default",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "provider",
            "is_active",
            "created_at",
            "updated_at",
            "receiver_account_masked",
            "has_card_token",
        ]

    def get_receiver_account_masked(
        self,
        obj: TeacherPayoutDestination,
    ) -> str:
        value = str(
            obj.receiver_account or ""
        ).strip()

        if not value:
            return ""

        if len(value) <= 8:
            return "*" * len(value)

        return (
            value[:4]
            + ("*" * (len(value) - 8))
            + value[-4:]
        )

    def get_has_card_token(
        self,
        obj: TeacherPayoutDestination,
    ) -> bool:
        return bool(
            str(
                obj.receiver_card_token or ""
            ).strip()
        )

    def validate(self, attrs):
        instance = self.instance

        destination_type = attrs.get(
            "destination_type",
            (
                instance.destination_type
                if instance
                else ""
            ),
        )

        destination_type = str(
            destination_type
        ).strip()

        account = attrs.get(
            "receiver_account",
            (
                instance.receiver_account
                if instance
                else ""
            ),
        )

        mfo = attrs.get(
            "receiver_mfo",
            (
                instance.receiver_mfo
                if instance
                else ""
            ),
        )

        okpo = attrs.get(
            "receiver_okpo",
            (
                instance.receiver_okpo
                if instance
                else ""
            ),
        )

        company = attrs.get(
            "receiver_company",
            (
                instance.receiver_company
                if instance
                else ""
            ),
        )

        card_token = attrs.get(
            "receiver_card_token",
            (
                instance.receiver_card_token
                if instance
                else ""
            ),
        )

        if (
            destination_type
            == TeacherPayoutDestination
            .TypeChoices
            .BANK_ACCOUNT
        ):
            missing = [
                key
                for key, value in {
                    "receiver_account": account,
                    "receiver_mfo": mfo,
                    "receiver_okpo": okpo,
                    "receiver_company": company,
                }.items()
                if not str(value or "").strip()
            ]

            if missing:
                raise serializers.ValidationError(
                    {
                        "detail": (
                            "Bank payout destination "
                            "is incomplete."
                        ),
                        "missing_fields": missing,
                    }
                )

            return attrs

        if (
            destination_type
            == TeacherPayoutDestination
            .TypeChoices
            .CARD_TOKEN
        ):
            token = str(
                card_token or ""
            ).strip()

            if not token:
                raise serializers.ValidationError(
                    {
                        "receiver_card_token": (
                            "LiqPay card token "
                            "is required."
                        )
                    }
                )

            self._reject_raw_card_number(
                token
            )

            return attrs

        raise serializers.ValidationError(
            {
                "destination_type": (
                    "Unsupported payout "
                    "destination type."
                )
            }
        )

    @staticmethod
    def _reject_raw_card_number(
        value: str,
    ) -> None:
        compact = (
            str(value or "")
            .replace(" ", "")
            .replace("-", "")
        )

        # Raw payment-card numbers are typically
        # 13-19 decimal digits.
        if (
            compact.isdigit()
            and 13 <= len(compact) <= 19
        ):
            raise serializers.ValidationError(
                {
                    "receiver_card_token": (
                        "Raw card numbers must "
                        "not be stored. Provide "
                        "a LiqPay card token."
                    )
                }
            )

    @transaction.atomic
    def create(self, validated_data):
        teacher = self.context[
            "request"
        ].user.teacher_profile

        is_default = bool(
            validated_data.pop(
                "is_default",
                False,
            )
        )

        has_active_destination = (
            TeacherPayoutDestination.objects
            .filter(
                teacher=teacher,
                provider="liqpay",
                is_active=True,
            )
            .exists()
        )

        destination = (
            TeacherPayoutDestination.objects.create(
                teacher=teacher,
                provider="liqpay",
                is_active=True,
                is_default=(
                    is_default
                    or not has_active_destination
                ),
                **validated_data,
            )
        )

        self._clear_irrelevant_fields(
            destination
        )

        if destination.is_default:
            self._clear_other_defaults(
                destination
            )

        return destination

    @transaction.atomic
    def update(
        self,
        instance,
        validated_data,
    ):
        requested_default = (
            validated_data.pop(
                "is_default",
                None,
            )
        )

        for field, value in (
            validated_data.items()
        ):
            setattr(
                instance,
                field,
                value,
            )

        if requested_default is True:
            instance.is_default = True

        instance.save()

        self._clear_irrelevant_fields(
            instance
        )

        if requested_default is True:
            self._clear_other_defaults(
                instance
            )

        # We deliberately do not allow a client
        # to unset the only default just by
        # sending is_default=false.
        return instance

    @staticmethod
    def _clear_other_defaults(
        destination,
    ) -> None:
        (
            TeacherPayoutDestination.objects
            .filter(
                teacher=destination.teacher,
                provider=destination.provider,
                is_default=True,
            )
            .exclude(pk=destination.pk)
            .update(is_default=False)
        )

    @staticmethod
    def _clear_irrelevant_fields(
        destination,
    ) -> None:
        if (
            destination.destination_type
            == TeacherPayoutDestination
            .TypeChoices
            .BANK_ACCOUNT
        ):
            if destination.receiver_card_token:
                destination.receiver_card_token = ""
                destination.save(
                    update_fields=[
                        "receiver_card_token",
                        "updated_at",
                    ]
                )

            return

        if (
            destination.destination_type
            == TeacherPayoutDestination
            .TypeChoices
            .CARD_TOKEN
        ):
            update_fields = []

            for field in (
                "receiver_account",
                "receiver_mfo",
                "receiver_okpo",
                "receiver_company",
            ):
                if getattr(destination, field):
                    setattr(
                        destination,
                        field,
                        "",
                    )
                    update_fields.append(field)

            if update_fields:
                update_fields.append(
                    "updated_at"
                )

                destination.save(
                    update_fields=update_fields
                )