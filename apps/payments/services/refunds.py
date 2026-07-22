from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.payments.models import Payment, Refund
from apps.users.models import User

from .exceptions import RefundError
from .stripe import StripeService


class RefundService(StripeService):
    @staticmethod
    def refunded_total(payment: Payment) -> Decimal:
        total = payment.refunds.filter(
            status=Refund.StatusChoices.SUCCEEDED,
        ).aggregate(total=Sum("amount"))["total"]
        return total or Decimal("0.00")

    @classmethod
    def refund_payment(
        cls,
        *,
        payment: Payment,
        amount: Decimal | None = None,
        reason: str = "",
        created_by: User | None = None,
    ) -> Payment:
        """Refund through Stripe, then record it.

        A refund that uses up the remaining refundable amount flips the payment
        to `refunded`; a partial one leaves it `succeeded` and only grows
        `refunded_amount`, so a partly refunded payment can be refunded again.
        """
        if payment.status == Payment.StatusChoices.REFUNDED:
            raise RefundError("Payment has already been refunded.")
        if not payment.can_be_refunded:
            raise RefundError("Only a successful payment can be refunded.")
        if not payment.stripe_payment_intent_id:
            raise RefundError(
                "Payment has no Stripe transaction to refund. Refund it in Stripe directly."
            )

        remaining = payment.amount - cls.refunded_total(payment)
        if amount is None:
            amount = remaining
        if amount > remaining:
            raise RefundError(
                f"Refund amount exceeds the {remaining} {payment.currency} "
                f"still refundable on this payment."
            )

        # Recorded before the Stripe call so a failed attempt leaves a trace,
        # and outside the transaction so no lock is held across the network hop.
        refund = Refund.objects.create(
            payment=payment,
            amount=amount,
            reason=reason,
            created_by=created_by,
        )
        try:
            stripe_refund = cls._create_stripe_refund(
                payment=payment,
                amount=amount,
                reason=reason,
            )
        except Exception:
            refund.status = Refund.StatusChoices.FAILED
            refund.save(update_fields=["status"])
            raise

        with transaction.atomic():
            refund.status = Refund.StatusChoices.SUCCEEDED
            refund.stripe_refund_id = getattr(stripe_refund, "id", "") or ""
            refund.processed_at = timezone.now()
            refund.save(update_fields=["status", "stripe_refund_id", "processed_at"])
            if amount >= remaining:
                payment.status = Payment.StatusChoices.REFUNDED
                payment.save(update_fields=["status", "updated_at"])

        return payment
