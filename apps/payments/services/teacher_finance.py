from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.payments.models import (
    Payment,
    Refund,
    TeacherLedgerEntry,
    TeacherPayout,
    TeacherPayoutDestination,
    TeacherPayoutItem,
)
from apps.users.models import TeacherProfile

from .base import PaymentBaseService
from .exceptions import PaymentError


class TeacherFinanceService(PaymentBaseService):
    @classmethod
    @transaction.atomic
    def ensure_payment_earning(
        cls,
        payment: Payment,
    ) -> TeacherLedgerEntry | None:
        """
        Create the teacher earning for a successfully
        processed LiqPay payment.

        Idempotent through TeacherLedgerEntry.source_key.
        """

        # Stripe legacy payments already transfer the
        # teacher share through Stripe Connect.
        if (
            payment.payment_method
            != Payment.MethodChoices.LIQPAY
        ):
            return None
        
        if (
            payment.status
            != Payment.StatusChoices.SUCCEEDED
        ):
            return None

        if payment.teacher_id is None:
            return None

        cls._lock_teacher(
            payment.teacher_id
        )

        teacher_amount = cls._decimal_money(
            Decimal(str(payment.teacher_amount))
        )

        if teacher_amount <= Decimal("0.00"):
            return None

        entry, _ = (
            TeacherLedgerEntry.objects.get_or_create(
                source_key=(
                    f"payment:{payment.id}:earning"
                ),
                defaults={
                    "teacher": payment.teacher,
                    "entry_type": (
                        TeacherLedgerEntry
                        .TypeChoices
                        .EARNING
                    ),
                    "status": (
                        TeacherLedgerEntry
                        .StatusChoices
                        .POSTED
                    ),
                    "amount": teacher_amount,
                    "currency": payment.currency.upper(),
                    "payment": payment,
                    "description": (
                        f"Earning from payment "
                        f"#{payment.id}"
                    ),
                },
            )
        )

        # Old/migrated row could theoretically exist
        # as PENDING. Make the operation self-healing.
        if (
            entry.status
            == TeacherLedgerEntry.StatusChoices.PENDING
        ):
            entry.post()

        return entry

    @staticmethod
    def _lock_teacher(
        teacher_id: int,
    ) -> TeacherProfile:
        return (
            TeacherProfile.objects
            .select_for_update()
            .get(pk=teacher_id)
        )

    @classmethod
    @transaction.atomic
    def ensure_refund_reservation(
        cls,
        refund: Refund,
    ) -> TeacherLedgerEntry | None:
        """
        Reserve the teacher's proportional share of a LiqPay refund.

        PENDING ledger entries reduce future available balance,
        but are not yet final accounting entries.
        """

        refund = (
            Refund.objects
            .select_for_update()
            .get(pk=refund.pk)
        )

        payment = (
            Payment.objects
            .select_for_update()
            .get(pk=refund.payment_id)
        )

        # Stripe legacy refunds already reverse the
        # Stripe Connect transfer.
        if (
            payment.payment_method
            != Payment.MethodChoices.LIQPAY
        ):
            return None

        if payment.teacher_id is None:
            return None

        cls._lock_teacher(
            payment.teacher_id
        )

        payment_amount = cls._decimal_money(
            Decimal(str(payment.amount))
        )

        teacher_amount = cls._decimal_money(
            Decimal(str(payment.teacher_amount))
        )

        if (
            payment_amount <= Decimal("0.00")
            or teacher_amount <= Decimal("0.00")
        ):
            return None

        source_key = (
            f"refund:{refund.id}:teacher"
        )

        existing = (
            TeacherLedgerEntry.objects
            .filter(source_key=source_key)
            .first()
        )

        if existing is not None:
            return existing

        # All money currently either refunded or reserved
        # for refund.
        refund_total = (
            payment.refunds
            .filter(
                status__in=[
                    Refund.StatusChoices.PENDING,
                    Refund.StatusChoices.SUCCEEDED,
                ]
            )
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0.00")
        )

        refund_total = min(
            cls._decimal_money(refund_total),
            payment_amount,
        )

        # Target teacher deduction after ALL currently
        # active refunds.
        target_teacher_refund = (
            teacher_amount
            * refund_total
            / payment_amount
        )

        target_teacher_refund = cls._decimal_money(
            target_teacher_refund
        )

        target_teacher_refund = min(
            target_teacher_refund,
            teacher_amount,
        )

        # Teacher refund ledger entries already reserved
        # or posted for this payment.
        existing_adjustments = (
            TeacherLedgerEntry.objects
            .filter(
                payment=payment,
                entry_type=(
                    TeacherLedgerEntry.TypeChoices.REFUND
                ),
                status__in=[
                    TeacherLedgerEntry.StatusChoices.PENDING,
                    TeacherLedgerEntry.StatusChoices.POSTED,
                ],
            )
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0.00")
        )

        # Refund entries are negative.
        already_reserved = abs(
            cls._decimal_money(existing_adjustments)
        )

        adjustment = cls._decimal_money(
            target_teacher_refund
            - already_reserved
        )

        if adjustment <= Decimal("0.00"):
            return None

        entry = TeacherLedgerEntry.objects.create(
            teacher_id=payment.teacher_id,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.REFUND
            ),
            status=(
                TeacherLedgerEntry.StatusChoices.PENDING
            ),
            amount=-adjustment,
            currency=payment.currency.upper(),
            payment=payment,
            refund=refund,
            source_key=source_key,
            description=(
                f"Refund adjustment for payment "
                f"#{payment.id}"
            ),
            metadata={
                "payment_amount": (
                    f"{payment_amount:.2f}"
                ),
                "teacher_amount": (
                    f"{teacher_amount:.2f}"
                ),
                "refund_amount": (
                    f"{refund.amount:.2f}"
                ),
            },
        )

        return entry


    @classmethod
    @transaction.atomic
    def post_refund_adjustment(
        cls,
        refund: Refund,
    ) -> TeacherLedgerEntry | None:
        entry = cls.ensure_refund_reservation(
            refund
        )

        if entry is None:
            return None

        if (
            entry.status
            == TeacherLedgerEntry.StatusChoices.VOID
        ):
            # A provider operation which was previously
            # considered failed must not silently revive.
            return entry

        entry.post()

        return entry


    @classmethod
    @transaction.atomic
    def void_refund_adjustment(
        cls,
        refund: Refund,
    ) -> TeacherLedgerEntry | None:
        entry = (
            TeacherLedgerEntry.objects
            .select_for_update()
            .filter(
                source_key=(
                    f"refund:{refund.id}:teacher"
                )
            )
            .first()
        )

        if entry is None:
            return None

        if (
            entry.status
            == TeacherLedgerEntry.StatusChoices.POSTED
        ):
            # Never erase finalized accounting silently.
            return entry

        entry.void()

        return entry


    @staticmethod
    def _sum_entries(queryset) -> Decimal:
        total = queryset.aggregate(
            total=Sum("amount")
        ).get("total")

        return total or Decimal("0.00")


    @classmethod
    def balance(
        cls,
        *,
        teacher,
        currency: str,
    ) -> dict:
        currency = str(currency).strip().upper()

        entries = TeacherLedgerEntry.objects.filter(
            teacher=teacher,
            currency=currency,
        )

        posted = entries.filter(
            status=TeacherLedgerEntry.StatusChoices.POSTED
        )

        pending = entries.filter(
            status=TeacherLedgerEntry.StatusChoices.PENDING
        )

        earned = cls._sum_entries(
            posted.filter(
                entry_type=(
                    TeacherLedgerEntry.TypeChoices.EARNING
                )
            )
        )

        refund_total = cls._sum_entries(
            posted.filter(
                entry_type=(
                    TeacherLedgerEntry.TypeChoices.REFUND
                )
            )
        )

        payout_total = cls._sum_entries(
            posted.filter(
                entry_type=(
                    TeacherLedgerEntry.TypeChoices.PAYOUT
                )
            )
        )

        adjustment_total = cls._sum_entries(
            posted.filter(
                entry_type=(
                    TeacherLedgerEntry.TypeChoices.ADJUSTMENT
                )
            )
        )

        posted_balance = cls._sum_entries(
            posted
        )

        # Only negative pending entries reserve money.
        # A future positive pending entry must NOT make
        # money available before it is actually posted.
        pending_negative = cls._sum_entries(
            pending.filter(
                amount__lt=Decimal("0.00")
            )
        )

        reserved = abs(pending_negative)

        available = cls._decimal_money(
            posted_balance - reserved
        )

        return {
            "currency": currency,
            "earned": cls._decimal_money(
                earned
            ),
            "refunded": cls._decimal_money(
                abs(refund_total)
            ),
            "paid": cls._decimal_money(
                abs(payout_total)
            ),
            "adjustments": cls._decimal_money(
                adjustment_total
            ),
            "reserved": cls._decimal_money(
                reserved
            ),
            "balance": cls._decimal_money(
                posted_balance
            ),
            "available": available,
        }
    
    @classmethod
    @transaction.atomic
    def reserve_payout(
        cls,
        *,
        teacher,
        destination: TeacherPayoutDestination,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
        created_by=None,
        provider: str = TeacherPayout.ProviderChoices.LIQPAY,
    ) -> TeacherPayout:
        amount = cls._decimal_money(
            Decimal(str(amount))
        )

        currency = str(currency).strip().upper()

        idempotency_key = str(
            idempotency_key
        ).strip()

        if amount <= Decimal("0.00"):
            raise PaymentError(
                "Payout amount must be positive."
            )

        if not currency:
            raise PaymentError(
                "Payout currency is required."
            )

        if not idempotency_key:
            raise PaymentError(
                "Payout idempotency key is required."
            )

        teacher = cls._lock_teacher(
            teacher.id
        )

        # Idempotent retry must return the original payout
        # when all immutable request parameters match.
        existing = (
            TeacherPayout.objects
            .filter(
                idempotency_key=idempotency_key
            )
            .first()
        )

        if existing is not None:
            if (
                existing.teacher_id != teacher.id
                or existing.destination_id != destination.id
                or existing.amount != amount
                or existing.currency != currency
                or existing.provider != provider
            ):
                raise PaymentError(
                    "Payout idempotency key is already "
                    "used for another payout."
                )

            return existing

        if destination.teacher_id != teacher.id:
            raise PaymentError(
                "Payout destination does not belong "
                "to this teacher."
            )

        if not destination.is_active:
            raise PaymentError(
                "Payout destination is inactive."
            )

        if destination.provider != provider:
            raise PaymentError(
                "Payout destination provider does "
                "not match payout provider."
            )

        cls._validate_payout_destination(
            destination
        )

        current_balance = cls.balance(
            teacher=teacher,
            currency=currency,
        )

        if (
            current_balance["available"]
            < amount
        ):
            raise PaymentError(
                "Payout amount exceeds the "
                f"available teacher balance of "
                f"{current_balance['available']:.2f} "
                f"{currency}."
            )

        destination_snapshot = {
            "destination_type": (
                destination.destination_type
            ),
        }

        if (
            destination.destination_type
            == TeacherPayoutDestination
            .TypeChoices
            .BANK_ACCOUNT
        ):
            destination_snapshot.update(
                {
                    "receiver_account": (
                        destination.receiver_account
                    ),
                    "receiver_mfo": (
                        destination.receiver_mfo
                    ),
                    "receiver_okpo": (
                        destination.receiver_okpo
                    ),
                    "receiver_company": (
                        destination.receiver_company
                    ),
                }
            )

        elif (
            destination.destination_type
            == TeacherPayoutDestination
            .TypeChoices
            .CARD_TOKEN
        ):
            destination_snapshot.update(
                {
                    "receiver_card_token": (
                        destination.receiver_card_token
                    ),
                }
            )

        payout = TeacherPayout.objects.create(
            teacher=teacher,
            destination=destination,
            destination_snapshot=destination_snapshot,
            amount=amount,
            currency=currency,
            provider=provider,
            status=TeacherPayout.StatusChoices.PENDING,
            idempotency_key=idempotency_key,
            created_by=created_by,
        )

        remaining = amount

        earning_entries = (
            TeacherLedgerEntry.objects
            .filter(
                teacher=teacher,
                currency=currency,
                entry_type=(
                    TeacherLedgerEntry
                    .TypeChoices
                    .EARNING
                ),
                status=(
                    TeacherLedgerEntry
                    .StatusChoices
                    .POSTED
                ),
                payment__isnull=False,
            )
            .select_related("payment")
            .order_by(
                "created_at",
                "id",
            )
        )

        active_payout_statuses = [
            TeacherPayout.StatusChoices.PENDING,
            TeacherPayout.StatusChoices.PROCESSING,
            TeacherPayout.StatusChoices.SUCCEEDED,
        ]

        for earning in earning_entries:
            if remaining <= Decimal("0.00"):
                break

            payment = earning.payment

            refund_adjustments = (
                TeacherLedgerEntry.objects
                .filter(
                    payment=payment,
                    entry_type=(
                        TeacherLedgerEntry
                        .TypeChoices
                        .REFUND
                    ),
                    status__in=[
                        TeacherLedgerEntry
                        .StatusChoices
                        .PENDING,
                        TeacherLedgerEntry
                        .StatusChoices
                        .POSTED,
                    ],
                )
                .aggregate(
                    total=Sum("amount")
                )
                .get("total")
                or Decimal("0.00")
            )

            already_allocated = (
                TeacherPayoutItem.objects
                .filter(
                    payment=payment,
                    payout__status__in=(
                        active_payout_statuses
                    ),
                )
                .aggregate(
                    total=Sum("amount")
                )
                .get("total")
                or Decimal("0.00")
            )

            source_available = cls._decimal_money(
                earning.amount
                + refund_adjustments
                - already_allocated
            )

            if source_available <= Decimal("0.00"):
                continue

            allocation = min(
                source_available,
                remaining,
            )

            allocation = cls._decimal_money(
                allocation
            )

            TeacherPayoutItem.objects.create(
                payout=payout,
                payment=payment,
                amount=allocation,
                currency=currency,
            )

            remaining = cls._decimal_money(
                remaining - allocation
            )

        if remaining != Decimal("0.00"):
            raise PaymentError(
                "Available teacher balance could "
                "not be allocated to source payments."
            )

        TeacherLedgerEntry.objects.create(
            teacher=teacher,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
            status=(
                TeacherLedgerEntry.StatusChoices.PENDING
            ),
            amount=-amount,
            currency=currency,
            payout=payout,
            source_key=(
                f"payout:{payout.id}:settlement"
            ),
            description=(
                f"Teacher payout #{payout.id}"
            ),
        )

        return payout

    
    @classmethod
    @transaction.atomic
    def mark_payout_processing(
        cls,
        payout: TeacherPayout,
        *,
        provider_status: str = "",
    ) -> TeacherPayout:
        cls._lock_teacher(
            payout.teacher_id
        )

        payout = (
            TeacherPayout.objects
            .select_for_update()
            .get(pk=payout.pk)
        )

        if (
            payout.status
            == TeacherPayout.StatusChoices.SUCCEEDED
        ):
            return payout

        if payout.status in {
            TeacherPayout.StatusChoices.FAILED,
            TeacherPayout.StatusChoices.CANCELED,
        }:
            raise PaymentError(
                "Finished payout cannot be moved "
                "to processing."
            )

        ledger = (
            TeacherLedgerEntry.objects
            .select_for_update()
            .filter(
                payout=payout,
                entry_type=(
                    TeacherLedgerEntry.TypeChoices.PAYOUT
                ),
            )
            .first()
        )

        if ledger is None:
            raise PaymentError(
                "Payout ledger reservation was not found."
            )

        if (
            ledger.status
            != TeacherLedgerEntry.StatusChoices.PENDING
        ):
            raise PaymentError(
                "Payout reservation is not pending."
            )

        payout.mark_as_processing(
            provider_status=provider_status,
        )

        return payout

    @staticmethod
    def _validate_payout_destination(
        destination: TeacherPayoutDestination,
    ) -> None:
        if (
            destination.destination_type
            == TeacherPayoutDestination
            .TypeChoices
            .BANK_ACCOUNT
        ):
            required = {
                "receiver_account": (
                    destination.receiver_account
                ),
                "receiver_mfo": (
                    destination.receiver_mfo
                ),
                "receiver_okpo": (
                    destination.receiver_okpo
                ),
                "receiver_company": (
                    destination.receiver_company
                ),
            }

            missing = [
                key
                for key, value in required.items()
                if not str(value).strip()
            ]

            if missing:
                raise PaymentError(
                    "Bank payout destination is "
                    "incomplete."
                )

            return

        if (
            destination.destination_type
            == TeacherPayoutDestination
            .TypeChoices
            .CARD_TOKEN
        ):
            if not destination.receiver_card_token:
                raise PaymentError(
                    "LiqPay card token is required."
                )

            return

        raise PaymentError(
            "Unsupported payout destination type."
        )
    
    @classmethod
    @transaction.atomic
    def mark_payout_succeeded(
        cls,
        payout: TeacherPayout,
        *,
        provider_status: str = "",
        provider_payment_id: str = "",
        provider_transaction_id: str = "",
    ) -> TeacherPayout:
        cls._lock_teacher(
            payout.teacher_id
        )

        payout = (
            TeacherPayout.objects
            .select_for_update()
            .get(pk=payout.pk)
        )

        if (
            payout.status
            == TeacherPayout.StatusChoices.SUCCEEDED
        ):
            return payout

        if payout.status in {
            TeacherPayout.StatusChoices.FAILED,
            TeacherPayout.StatusChoices.CANCELED,
        }:
            raise PaymentError(
                "Failed or canceled payout cannot "
                "be marked as succeeded."
            )

        ledger = (
            TeacherLedgerEntry.objects
            .select_for_update()
            .filter(
                payout=payout,
                entry_type=(
                    TeacherLedgerEntry.TypeChoices.PAYOUT
                ),
            )
            .first()
        )

        if ledger is None:
            raise PaymentError(
                "Payout ledger reservation was not found."
            )

        if (
            ledger.status
            == TeacherLedgerEntry.StatusChoices.VOID
        ):
            raise PaymentError(
                "Voided payout reservation cannot "
                "be settled."
            )

        if (
            ledger.status
            == TeacherLedgerEntry.StatusChoices.PENDING
        ):
            ledger.post()

        payout.mark_as_succeeded(
            provider_status=provider_status,
            provider_payment_id=provider_payment_id,
            provider_transaction_id=(
                provider_transaction_id
            ),
        )

        return payout

    @classmethod
    @transaction.atomic
    def mark_payout_failed(
        cls,
        payout: TeacherPayout,
        *,
        provider_status: str = "",
        reason: str = "",
    ) -> TeacherPayout:
        cls._lock_teacher(
            payout.teacher_id
        )

        payout = (
            TeacherPayout.objects
            .select_for_update()
            .get(pk=payout.pk)
        )

        if (
            payout.status
            == TeacherPayout.StatusChoices.FAILED
        ):
            return payout

        if (
            payout.status
            == TeacherPayout.StatusChoices.SUCCEEDED
        ):
            raise PaymentError(
                "Successful payout cannot be "
                "marked as failed."
            )

        if (
            payout.status
            == TeacherPayout.StatusChoices.CANCELED
        ):
            return payout

        ledger = (
            TeacherLedgerEntry.objects
            .select_for_update()
            .filter(
                payout=payout,
                entry_type=(
                    TeacherLedgerEntry.TypeChoices.PAYOUT
                ),
            )
            .first()
        )

        if ledger is None:
            raise PaymentError(
                "Payout ledger reservation was not found."
            )

        if (
            ledger.status
            == TeacherLedgerEntry.StatusChoices.POSTED
        ):
            raise PaymentError(
                "Settled payout ledger entry cannot "
                "be voided."
            )

        if (
            ledger.status
            == TeacherLedgerEntry.StatusChoices.PENDING
        ):
            ledger.void()

        payout.mark_as_failed(
            provider_status=provider_status,
            reason=reason,
        )

        return payout
