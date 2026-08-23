from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.payments.models import Payment, Refund
from apps.users.models import User

from .exceptions import PaymentError, RefundError
from .liqpay import LiqPayService
from .stripe import StripeService
from .teacher_finance import TeacherFinanceService


class RefundService(StripeService):
    @staticmethod
    def refunded_total(payment: Payment) -> Decimal:
        """
        Money that has actually been successfully refunded.
        """
        total = (
            payment.refunds.filter(
                status=Refund.StatusChoices.SUCCEEDED,
            )
            .aggregate(total=Sum("amount"))
            .get("total")
        )
        return total or Decimal("0.00")

    @classmethod
    @transaction.atomic
    def _store_liqpay_refund_reconciliation(
        cls,
        *,
        refund: Refund,
        payload: dict,
    ) -> Refund:
        refund = (
            Refund.objects
            .select_for_update()
            .select_related("payment")
            .get(pk=refund.pk)
        )

        if (
            refund.status
            != Refund.StatusChoices.PENDING
        ):
            return refund

        payment = refund.payment

        expected_order_id = str(
            (refund.metadata or {}).get(
                "provider_order_id",
                "",
            )
        ).strip()

        response_order_id = str(
            payload.get("order_id") or ""
        ).strip()

        if (
            response_order_id
            and response_order_id
            != expected_order_id
        ):
            raise PaymentError(
                "LiqPay refund reconciliation "
                "order_id does not match."
            )

        response_public_key = (
            payload.get("public_key")
        )

        if (
            response_public_key
            and response_public_key
            != LiqPayService._liqpay_public_key()
        ):
            raise PaymentError(
                "LiqPay refund reconciliation "
                "public_key does not match."
            )

        response_version = payload.get(
            "version"
        )

        if response_version is not None:
            try:
                version = int(
                    response_version
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise PaymentError(
                    "Invalid LiqPay refund "
                    "reconciliation API version."
                ) from exc

            if (
                version
                != LiqPayService._liqpay_api_version()
            ):
                raise PaymentError(
                    "LiqPay refund reconciliation "
                    "API version does not match."
                )

        # status API returns information about
        # the ORIGINAL payment.
        action = str(
            payload.get("action") or ""
        ).strip().lower()

        if (
            action
            and action != "pay"
        ):
            raise PaymentError(
                "Unexpected LiqPay payment "
                "action during refund "
                "reconciliation."
            )

        if payload.get("amount") is not None:
            try:
                provider_amount = (
                    cls._decimal_money(
                        Decimal(
                            str(
                                payload["amount"]
                            )
                        )
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise PaymentError(
                    "Invalid LiqPay payment "
                    "amount during refund "
                    "reconciliation."
                ) from exc

            expected_amount = (
                cls._decimal_money(
                    Decimal(
                        str(payment.amount)
                    )
                )
            )

            if provider_amount != expected_amount:
                raise PaymentError(
                    "LiqPay payment amount "
                    "does not match refund payment."
                )

        if payload.get("currency"):
            provider_currency = str(
                payload["currency"]
            ).strip().upper()

            if (
                provider_currency
                != payment.currency.upper()
            ):
                raise PaymentError(
                    "LiqPay payment currency "
                    "does not match refund payment."
                )

        provider_status = str(
            payload.get("status") or ""
        ).strip().lower()

        refund.provider_status = (
            provider_status
        )

        if payload.get("payment_id") is not None:
            refund.provider_reference = str(
                payload["payment_id"]
            )

        refund.metadata = {
            **(refund.metadata or {}),
            "last_reconciliation": (
                timezone.now().isoformat()
            ),
            "last_reconciliation_status": (
                provider_status
            ),
            "wait_reserve_status": (
                payload.get(
                    "wait_reserve_status"
                )
            ),
            "liqpay_order_id": (
                payload.get(
                    "liqpay_order_id"
                )
            ),
        }

        refund.save(
            update_fields=[
                "provider_status",
                "provider_reference",
                "metadata",
            ]
        )

        return refund

    @staticmethod
    def reserved_refund_total(payment: Payment) -> Decimal:
        """
        Money that is either already refunded or currently reserved
        by an in-progress refund request.

        PENDING refunds count here so two concurrent requests cannot
        refund the same money twice.
        """
        total = (
            payment.refunds.filter(
                status__in=[
                    Refund.StatusChoices.PENDING,
                    Refund.StatusChoices.SUCCEEDED,
                ],
            )
            .aggregate(total=Sum("amount"))
            .get("total")
        )
        return total or Decimal("0.00")

    @classmethod
    def reconcile_liqpay_refund(
        cls,
        *,
        refund: Refund,
    ) -> Refund:
        refund = (
            Refund.objects
            .select_related(
                "payment",
            )
            .get(pk=refund.pk)
        )

        if (
            refund.provider
            != Payment.MethodChoices.LIQPAY
        ):
            raise RefundError(
                "This is not a LiqPay refund."
            )

        if refund.status in {
            Refund.StatusChoices.SUCCEEDED,
            Refund.StatusChoices.FAILED,
            Refund.StatusChoices.CANCELED,
        }:
            return refund

        if (
            refund.status
            != Refund.StatusChoices.PENDING
        ):
            raise RefundError(
                "Only pending LiqPay refund "
                "can be reconciled."
            )

        metadata = refund.metadata or {}

        provider_order_id = str(
            metadata.get(
                "provider_order_id",
                "",
            )
        ).strip()

        if not provider_order_id:
            raise RefundError(
                "Refund provider_order_id "
                "was not recorded."
            )

        # IMPORTANT:
        # network request outside transaction/row lock.
        payload = (
            LiqPayService
            ._liqpay_get_payment_status(
                provider_order_id=(
                    provider_order_id
                )
            )
        )

        refund = (
            cls
            ._store_liqpay_refund_reconciliation(
                refund=refund,
                payload=payload,
            )
        )

        if (
            refund.status
            != Refund.StatusChoices.PENDING
        ):
            return refund

        provider_status = str(
            refund.provider_status or ""
        ).strip().lower()

        # This is the only payment-level state
        # that conclusively proves the original
        # payment has been refunded.
        if provider_status != "reversed":
            return refund

        metadata = refund.metadata or {}

        is_full_remaining_refund = bool(
            metadata.get(
                "is_full_remaining_refund",
                False,
            )
        )

        # For a partial refund, "reversed" cannot
        # safely be attributed to this specific
        # Refund row without stronger provider
        # correlation.
        if not is_full_remaining_refund:
            refund.metadata = {
                **metadata,
                "reconciliation_requires_review": (
                    True
                ),
            }

            refund.save(
                update_fields=[
                    "metadata",
                ]
            )

            return refund

        remaining_before_raw = metadata.get(
            "successful_remaining_before"
        )

        if remaining_before_raw is None:
            raise RefundError(
                "Refund reconciliation snapshot "
                "is incomplete."
            )

        try:
            successful_remaining_before = (
                cls._decimal_money(
                    Decimal(
                        str(
                            remaining_before_raw
                        )
                    )
                )
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise RefundError(
                "Invalid refund reconciliation "
                "snapshot."
            ) from exc

        cls._mark_refund_succeeded(
                refund=refund,
                payment=refund.payment,
                successful_remaining_before=(
                    successful_remaining_before
                ),
                provider_reference=(
                    refund.provider_reference
                ),
                provider_status="reversed",
                metadata={
                    "request_uncertain": False,
                    "reconciled": True,
                    "reconciliation_requires_review": (
                        False
                    ),
                },
            )

        refund.refresh_from_db()

        return refund

    @classmethod
    def refundable_remaining(
        cls,
        payment: Payment,
    ) -> Decimal:
        remaining = (
            payment.amount
            - cls.reserved_refund_total(payment)
        )
        return max(
            remaining,
            Decimal("0.00"),
        )

    @classmethod
    def _prepare_refund(
        cls,
        *,
        payment: Payment,
        amount: Decimal | None,
        reason: str,
        created_by: User | None,
    ) -> tuple[Payment, Refund, Decimal]:
        """
        Validate and reserve refund amount under a Payment row lock.

        Returns:
            payment
            refund
            successfully_refundable_before_this_refund
        """
        with transaction.atomic():
            payment = (
                Payment.objects
                .select_for_update()
                .get(pk=payment.pk)
            )

            if payment.status == Payment.StatusChoices.REFUNDED:
                raise RefundError(
                    "Payment has already been refunded."
                )

            if not payment.can_be_refunded:
                raise RefundError(
                    "Only a successful payment can be refunded."
                )
            pending_refund = (
                payment.refunds
                .filter(
                    status=Refund.StatusChoices.PENDING,
                )
                .exists()
            )

            if pending_refund:
                raise RefundError(
                    "This payment already has a "
                    "pending refund."
                )
            
            successfully_refunded = cls.refunded_total(
                payment
            )

            successful_remaining = (
                payment.amount
                - successfully_refunded
            )

            available = cls.refundable_remaining(
                payment
            )

            if amount is None:
                amount = available
            else:
                amount = cls._decimal_money(
                    Decimal(str(amount))
                )

            if amount <= Decimal("0.00"):
                raise RefundError(
                    "Refund amount must be positive."
                )

            if amount > available:
                raise RefundError(
                    f"Refund amount exceeds the "
                    f"{available} {payment.currency} "
                    f"currently refundable on this payment."
                )

            refund = Refund.objects.create(
                payment=payment,
                amount=amount,
                reason=reason,
                created_by=created_by,
                provider=payment.payment_method,
                status=Refund.StatusChoices.PENDING,
            )
            TeacherFinanceService.ensure_refund_reservation(
                refund
            )

            return (
                payment,
                refund,
                successful_remaining,
            )

    @classmethod
    def _mark_refund_succeeded(
        cls,
        *,
        refund: Refund,
        payment: Payment,
        successful_remaining_before: Decimal,
        provider_reference: str = "",
        provider_status: str = "",
        metadata: dict | None = None,
        stripe_refund_id: str = "",
    ) -> Payment:
        with transaction.atomic():
            refund = (
                Refund.objects
                .select_for_update()
                .get(pk=refund.pk)
            )

            payment = (
                Payment.objects
                .select_for_update()
                .get(pk=payment.pk)
            )

            if refund.status == Refund.StatusChoices.SUCCEEDED:
                return payment

            refund.status = Refund.StatusChoices.SUCCEEDED
            refund.provider_reference = provider_reference
            refund.provider_status = provider_status
            refund.metadata = {
                **(refund.metadata or {}),
                **(metadata or {}),
            }
            refund.processed_at = timezone.now()

            update_fields = [
                "status",
                "provider_reference",
                "provider_status",
                "metadata",
                "processed_at",
            ]

            if stripe_refund_id:
                refund.stripe_refund_id = stripe_refund_id
                update_fields.append(
                    "stripe_refund_id"
                )

            refund.save(
                update_fields=update_fields
            )

            TeacherFinanceService.post_refund_adjustment(
                refund
            )

            if (
                refund.amount
                >= successful_remaining_before
            ):
                payment.status = (
                    Payment.StatusChoices.REFUNDED
                )
                payment.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

            return payment

    @classmethod
    def _mark_refund_failed(
        cls,
        *,
        refund: Refund,
        provider_status: str = "",
        metadata: dict | None = None,
    ) -> None:
        refund.status = Refund.StatusChoices.FAILED
        refund.provider_status = provider_status
        refund.metadata = {
            **(refund.metadata or {}),
            **(metadata or {}),
        }
        refund.processed_at = timezone.now()

        refund.save(
            update_fields=[
                "status",
                "provider_status",
                "metadata",
                "processed_at",
            ]
        )

        TeacherFinanceService.void_refund_adjustment(
            refund
        )

    @classmethod
    @transaction.atomic
    def _mark_refund_request_uncertain(
        cls,
        *,
        refund: Refund,
    ) -> None:
        refund = (
            Refund.objects
            .select_for_update()
            .get(pk=refund.pk)
        )

        if (
            refund.status
            != Refund.StatusChoices.PENDING
        ):
            return

        refund.provider_status = (
            "request_uncertain"
        )

        refund.metadata = {
            **(refund.metadata or {}),
            "request_uncertain": True,
        }

        # processed_at intentionally remains NULL:
        # the provider outcome is not final.
        refund.save(
            update_fields=[
                "provider_status",
                "metadata",
            ]
        )

    @classmethod
    def _refund_stripe_payment(
        cls,
        *,
        payment: Payment,
        refund: Refund,
        successful_remaining_before: Decimal,
        reason: str,
    ) -> Payment:
        if not payment.stripe_payment_intent_id:
            cls._mark_refund_failed(
                refund=refund,
                provider_status="missing_payment_intent",
            )

            raise RefundError(
                "Payment has no Stripe transaction to refund."
            )

        try:
            stripe_refund = cls._create_stripe_refund(
                payment=payment,
                amount=refund.amount,
                reason=reason,
                idempotency_key=f"refund-{refund.id}",
            )
        except Exception:
            cls._mark_refund_failed(
                refund=refund,
                provider_status="request_failed",
            )
            raise

        stripe_refund_id = (
            getattr(
                stripe_refund,
                "id",
                "",
            )
            or ""
        )

        stripe_status = (
            getattr(
                stripe_refund,
                "status",
                "",
            )
            or "succeeded"
        )

        return cls._mark_refund_succeeded(
            refund=refund,
            payment=payment,
            successful_remaining_before=(
                successful_remaining_before
            ),
            provider_reference=stripe_refund_id,
            provider_status=stripe_status,
            stripe_refund_id=stripe_refund_id,
        )

    @classmethod
    def _refund_liqpay_payment(
        cls,
        *,
        payment: Payment,
        refund: Refund,
        successful_remaining_before: Decimal,
    ) -> Payment:
        attempt = (
            LiqPayService
            ._liqpay_refundable_attempt(
                payment=payment,
            )
        )

        is_full_remaining_refund = (
            cls._decimal_money(
                Decimal(str(refund.amount))
            )
            >= cls._decimal_money(
                Decimal(
                    str(
                        successful_remaining_before
                    )
                )
            )
        )

        refund.metadata = {
            **(refund.metadata or {}),
            "provider_order_id": (
                attempt.provider_order_id
            ),
            "successful_remaining_before": (
                str(
                    cls._decimal_money(
                        Decimal(
                            str(
                                successful_remaining_before
                            )
                        )
                    )
                )
            ),
            "is_full_remaining_refund": (
                is_full_remaining_refund
            ),
        }

        refund.save(
            update_fields=[
                "metadata",
            ]
        )

        try:
            response = (
                LiqPayService
                ._liqpay_create_refund(
                    provider_order_id=(
                        attempt.provider_order_id
                    ),
                    amount=refund.amount,
                )
            )
        except Exception:
            cls._mark_refund_request_uncertain(
                refund=refund,
            )
            raise

        result = str(
            response.get("result") or ""
        ).lower()

        provider_status = str(
            response.get("status") or ""
        ).lower()

        provider_reference = str(
            response.get("payment_id") or ""
        )

        metadata = {
            "liqpay_result": result,
            "wait_amount": response.get(
                "wait_amount"
            ),
            "provider_order_id": (
                attempt.provider_order_id
            ),
        }

        if result != "ok":
            cls._mark_refund_failed(
                refund=refund,
                provider_status=(
                    provider_status
                    or "error"
                ),
                metadata=metadata,
            )

            raise PaymentError(
                "LiqPay rejected the refund request."
            )

        if provider_status in {
            "error",
            "failure",
        }:
            cls._mark_refund_failed(
                refund=refund,
                provider_status=provider_status,
                metadata=metadata,
            )

            raise PaymentError(
                "LiqPay refund failed."
            )

        if provider_status == "reversed":
            return cls._mark_refund_succeeded(
                refund=refund,
                payment=payment,
                successful_remaining_before=(
                    successful_remaining_before
                ),
                provider_reference=(
                    provider_reference
                ),
                provider_status=provider_status,
                metadata=metadata,
            )

        # LiqPay accepted the request,
        # but the refund is not final yet.
        refund.provider_reference = (
            provider_reference
        )
        refund.provider_status = (
            provider_status
        )
        refund.metadata = {
            **(refund.metadata or {}),
            **metadata,
        }

        refund.save(
            update_fields=[
                "provider_reference",
                "provider_status",
                "metadata",
            ]
        )

        return payment

    @classmethod
    def refund_payment(
        cls,
        *,
        payment: Payment,
        amount: Decimal | None = None,
        reason: str = "",
        created_by: User | None = None,
    ) -> Payment:
        payment, refund, successful_remaining = (
            cls._prepare_refund(
                payment=payment,
                amount=amount,
                reason=reason,
                created_by=created_by,
            )
        )

        if (
            payment.payment_method
            == Payment.MethodChoices.STRIPE
        ):
            return cls._refund_stripe_payment(
                payment=payment,
                refund=refund,
                successful_remaining_before=(
                    successful_remaining
                ),
                reason=reason,
            )

        if (
            payment.payment_method
            == Payment.MethodChoices.LIQPAY
        ):
            return cls._refund_liqpay_payment(
                payment=payment,
                refund=refund,
                successful_remaining_before=(
                    successful_remaining
                ),
            )

        cls._mark_refund_failed(
            refund=refund,
            provider_status="unsupported_provider",
        )

        raise RefundError(
            "This payment provider does not support automatic refunds."
        )