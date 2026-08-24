import hashlib
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.cart.models import CartItem
from apps.enrollments.models import Enrollment
from apps.enrollments.services import EnrollmentService
from apps.payments.models import (
    Order,
    Payment,
    PaymentAttempt,
    PaymentInstallment,
    TeacherPayoutAccount,
    WebhookEvent,
)

from .base import PaymentBaseService
from .exceptions import PaymentError
from .teacher_finance import TeacherFinanceService


class WebhookService(PaymentBaseService):
    @classmethod
    def record_stripe_event(cls, event_data: dict) -> tuple[WebhookEvent, bool]:
        return WebhookEvent.objects.get_or_create(
            provider=WebhookEvent.ProviderChoices.STRIPE,
            event_id=event_data["id"],
            defaults={
                "event_type": event_data["type"],
                "data": event_data,
            },
        )

    @classmethod
    def record_liqpay_event(
        cls,
        *,
        data: str,
        payload: dict,
    ) -> tuple[WebhookEvent, bool]:
        event_id = hashlib.sha256(data.encode("utf-8")).hexdigest()

        provider_status = str(payload.get("status") or "")

        safe_data = {
            "order_id": payload.get("order_id"),
            "status": provider_status,
            "payment_id": payload.get("payment_id"),
            "transaction_id": payload.get("transaction_id"),
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
            "action": payload.get("action"),
            "version": payload.get("version"),
            "liqpay_order_id": payload.get("liqpay_order_id"),
            "paytype": payload.get("paytype"),
        }

        return WebhookEvent.objects.get_or_create(
            provider=WebhookEvent.ProviderChoices.LIQPAY,
            event_id=event_id,
            defaults={
                "event_type": f"liqpay.{provider_status}",
                "data": safe_data,
            },
        )

    @classmethod
    @transaction.atomic
    def handle_liqpay_callback(
        cls,
        *,
        data: str,
        signature: str,
    ) -> Payment:
        if not data or not signature:
            raise PaymentError("LiqPay callback data and signature are required.")

        # 1. Signature MUST be checked before trusting callback data.
        if not cls._liqpay_verify_signature(
            data=data,
            signature=signature,
        ):
            raise PaymentError("Invalid LiqPay callback signature.")

        payload = cls._liqpay_decode_data(data)

        provider_order_id = str(payload.get("order_id") or "")
        provider_status = str(payload.get("status") or "").lower()

        if not provider_order_id:
            raise PaymentError("LiqPay callback order_id is missing.")

        if not provider_status:
            raise PaymentError("LiqPay callback status is missing.")

        # 2. Callback must belong to our merchant.
        if payload.get("public_key") != cls._liqpay_public_key():
            raise PaymentError("LiqPay callback public_key does not match.")

        try:
            version = int(payload.get("version"))
        except (TypeError, ValueError) as exc:
            raise PaymentError("Invalid LiqPay callback version.") from exc

        if version != cls._liqpay_api_version():
            raise PaymentError("LiqPay callback API version does not match.")

        action = str(payload.get("action") or "").lower()

        if action and action != "pay":
            raise PaymentError("Unexpected LiqPay callback action.")

        # 3. Lock our existing provider attempt.
        attempt = (
            PaymentAttempt.objects.select_for_update(of=("self",))
            .filter(
                provider=Payment.MethodChoices.LIQPAY,
                provider_order_id=provider_order_id,
            )
            .first()
        )

        if attempt is None:
            raise PaymentError("LiqPay payment attempt was not found.")

        # 4. Lock actual Payment separately.
        payment = (
            Payment.objects.select_for_update(of=("self",))
            .select_related(
                "order",
                "installment",
            )
            .get(pk=attempt.payment_id)
        )

        if payment.payment_method != Payment.MethodChoices.LIQPAY:
            raise PaymentError("Payment provider does not match LiqPay.")

        # 5. Validate amount.
        try:
            callback_amount = cls._decimal_money(Decimal(str(payload.get("amount"))))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise PaymentError("Invalid LiqPay callback amount.") from exc

        expected_amount = cls._decimal_money(payment.amount)

        if callback_amount != expected_amount:
            raise PaymentError("LiqPay callback amount does not match payment.")

        # 6. Validate currency.
        callback_currency = str(payload.get("currency") or "").upper()

        if callback_currency != payment.currency.upper():
            raise PaymentError("LiqPay callback currency does not match payment.")

        # 7. Record callback only AFTER validation.
        webhook_event, _ = cls.record_liqpay_event(
            data=data,
            payload=payload,
        )

        if webhook_event.status == WebhookEvent.StatusChoices.PROCESSED:
            return payment

        payment, _ = cls._apply_liqpay_payment_status(
            provider_order_id=provider_order_id,
            payload=payload,
        )

        webhook_event.mark_as_processed()

        return payment

    @classmethod
    @transaction.atomic
    def _apply_liqpay_payment_status(
        cls,
        *,
        provider_order_id: str,
        payload: dict,
    ) -> tuple[Payment, str]:
        provider_status = str(payload.get("status") or "").lower()

        if not provider_status:
            raise PaymentError("LiqPay payment status is missing.")

        attempt = (
            PaymentAttempt.objects.select_for_update(of=("self",))
            .filter(
                provider=Payment.MethodChoices.LIQPAY,
                provider_order_id=provider_order_id,
            )
            .first()
        )

        if attempt is None:
            raise PaymentError("LiqPay payment attempt was not found.")

        payment = (
            Payment.objects.select_for_update(of=("self",))
            .select_related(
                "order",
                "installment",
            )
            .get(pk=attempt.payment_id)
        )

        if payment.payment_method != Payment.MethodChoices.LIQPAY:
            raise PaymentError("Payment provider does not match LiqPay.")

        response_order_id = str(payload.get("order_id") or "")

        if response_order_id and response_order_id != provider_order_id:
            raise PaymentError("LiqPay order_id does not match payment attempt.")

        response_public_key = payload.get("public_key")

        if response_public_key and response_public_key != cls._liqpay_public_key():
            raise PaymentError("LiqPay public_key does not match.")

        response_version = payload.get("version")

        if response_version is not None:
            try:
                version = int(response_version)
            except (TypeError, ValueError) as exc:
                raise PaymentError("Invalid LiqPay API version.") from exc

            if version != cls._liqpay_api_version():
                raise PaymentError("LiqPay API version does not match.")

        # Status API normally returns payment amount/currency.
        # Validate them whenever LiqPay included them.
        if payload.get("amount") is not None:
            try:
                provider_amount = cls._decimal_money(Decimal(str(payload["amount"])))
            except (
                InvalidOperation,
                TypeError,
                ValueError,
            ) as exc:
                raise PaymentError("Invalid LiqPay payment amount.") from exc

            expected_amount = cls._decimal_money(payment.amount)

            if provider_amount != expected_amount:
                raise PaymentError("LiqPay payment amount does not match.")

        if payload.get("currency"):
            provider_currency = str(payload["currency"]).upper()

            if provider_currency != payment.currency.upper():
                raise PaymentError("LiqPay payment currency does not match.")

        attempt.provider_status = provider_status

        if payload.get("payment_id") is not None:
            attempt.provider_payment_id = str(payload["payment_id"])

        if payload.get("transaction_id") is not None:
            attempt.provider_transaction_id = str(payload["transaction_id"])

        attempt.metadata = {
            **(attempt.metadata or {}),
            "last_liqpay_status_sync": (timezone.now().isoformat()),
            "liqpay_action": payload.get("action"),
            "liqpay_paytype": payload.get("paytype"),
            "liqpay_order_id": payload.get("liqpay_order_id"),
        }

        is_sandbox_success = provider_status == "sandbox" and cls._liqpay_public_key().startswith(
            "sandbox_"
        )

        # SUCCESS
        if provider_status == "success" or is_sandbox_success:
            attempt.status = Payment.StatusChoices.SUCCEEDED

            if attempt.processed_at is None:
                attempt.processed_at = timezone.now()

            attempt.save(
                update_fields=[
                    "provider_status",
                    "provider_payment_id",
                    "provider_transaction_id",
                    "status",
                    "processed_at",
                    "metadata",
                    "updated_at",
                ]
            )

            # Never turn an already-refunded payment
            # back into succeeded.
            if payment.status != Payment.StatusChoices.REFUNDED:
                payment = cls._complete_successful_payment(
                    payment,
                    record_attempt=False,
                )

            return payment, provider_status

        # FAILURE
        if provider_status in {
            "failure",
            "error",
        }:
            attempt.status = Payment.StatusChoices.FAILED

            if attempt.processed_at is None:
                attempt.processed_at = timezone.now()

            attempt.save(
                update_fields=[
                    "provider_status",
                    "provider_payment_id",
                    "provider_transaction_id",
                    "status",
                    "processed_at",
                    "metadata",
                    "updated_at",
                ]
            )

            if payment.status not in {
                Payment.StatusChoices.SUCCEEDED,
                Payment.StatusChoices.REFUNDED,
            }:
                payment.mark_as_failed(f"LiqPay payment finished with status: {provider_status}.")

                if payment.installment_id:
                    payment.installment.mark_as_failed()

            return payment, provider_status

        # REVERSED
        if provider_status == "reversed":
            attempt.status = Payment.StatusChoices.CANCELED

            if attempt.processed_at is None:
                attempt.processed_at = timezone.now()

            attempt.save(
                update_fields=[
                    "provider_status",
                    "provider_payment_id",
                    "provider_transaction_id",
                    "status",
                    "processed_at",
                    "metadata",
                    "updated_at",
                ]
            )

            # If it was already successfully paid,
            # reversal/refund is handled by Refund flow.
            if payment.status not in {
                Payment.StatusChoices.SUCCEEDED,
                Payment.StatusChoices.REFUNDED,
            }:
                payment.mark_as_canceled("LiqPay payment was reversed.")

            return payment, provider_status

        # Any non-final provider state.
        attempt.status = Payment.StatusChoices.PROCESSING

        attempt.save(
            update_fields=[
                "provider_status",
                "provider_payment_id",
                "provider_transaction_id",
                "status",
                "metadata",
                "updated_at",
            ]
        )

        return payment, provider_status

    @classmethod
    def sync_liqpay_payment_status(
        cls,
        *,
        payment: Payment,
    ) -> tuple[Payment, str]:
        if payment.payment_method != Payment.MethodChoices.LIQPAY:
            raise PaymentError("This payment is not a LiqPay payment.")

        attempt = (
            payment.attempts.filter(
                provider=Payment.MethodChoices.LIQPAY,
            )
            .exclude(provider_order_id="")
            .order_by("-created_at")
            .first()
        )

        if attempt is None:
            raise PaymentError("LiqPay payment attempt was not found.")

        # IMPORTANT:
        # network call happens OUTSIDE DB transaction/row lock.
        payload = cls._liqpay_get_payment_status(provider_order_id=(attempt.provider_order_id))

        return cls._apply_liqpay_payment_status(
            provider_order_id=(attempt.provider_order_id),
            payload=payload,
        )

    @classmethod
    @transaction.atomic
    def process_webhook_event(cls, webhook_event: WebhookEvent) -> None:
        if webhook_event.status == WebhookEvent.StatusChoices.PROCESSED:
            return

        try:
            if webhook_event.event_type == "checkout.session.completed":
                cls.handle_checkout_session_completed(webhook_event.data["data"]["object"])
                webhook_event.mark_as_processed()
                return

            if webhook_event.event_type == "checkout.session.expired":
                cls.handle_checkout_session_expired(webhook_event.data["data"]["object"])
                webhook_event.mark_as_processed()
                return

            if webhook_event.event_type == "checkout.session.async_payment_failed":
                cls.handle_checkout_session_failed(webhook_event.data["data"]["object"])
                webhook_event.mark_as_processed()
                return

            if webhook_event.event_type == "payment_intent.succeeded":
                cls.handle_payment_intent_succeeded(webhook_event.data["data"]["object"])
                webhook_event.mark_as_processed()
                return

            if webhook_event.event_type == "payment_intent.payment_failed":
                cls.handle_payment_intent_failed(webhook_event.data["data"]["object"])
                webhook_event.mark_as_processed()
                return

            if webhook_event.event_type == "account.updated":
                account = webhook_event.data["data"]["object"]
                payout = TeacherPayoutAccount.objects.filter(
                    provider_account_id=account["id"]
                ).first()
                if payout:
                    cls.sync_account(payout, account)
                webhook_event.mark_as_processed()
                return

            webhook_event.mark_as_ignored()
        except Exception as exc:
            webhook_event.mark_as_failed(str(exc))
            raise

    @classmethod
    def _complete_successful_payment(
        cls,
        payment: Payment,
        *,
        payment_intent_id: str = "",
        customer_id: str = "",
        attempt_metadata: dict | None = None,
        charge_id: str = "",
        record_attempt: bool = True,
    ) -> Payment:
        if payment.status == Payment.StatusChoices.SUCCEEDED:
            TeacherFinanceService.ensure_payment_earning(payment)
            return payment

        payment.mark_as_succeeded(
            payment_intent_id=payment_intent_id,
            customer_id=customer_id,
        )
        TeacherFinanceService.ensure_payment_earning(payment)

        if charge_id and payment.stripe_charge_id != charge_id:
            payment.stripe_charge_id = charge_id
            payment.save(update_fields=["stripe_charge_id", "updated_at"])

        if payment.installment_id:
            payment.installment.mark_as_paid()

        if payment.order_id:
            payment.order.sync_status_from_payments()

        if cls._payment_should_grant_access(payment):
            cls._grant_enrollments(payment)
            cls._remove_paid_items_from_cart(payment)
        if record_attempt:
            PaymentAttempt.objects.get_or_create(
                payment=payment,
                status=Payment.StatusChoices.SUCCEEDED,
                defaults={
                    "metadata": attempt_metadata or {},
                    "stripe_charge_id": charge_id,
                },
            )
        return payment

    @staticmethod
    def _payment_should_grant_access(payment: Payment) -> bool:
        if payment.order_id is None:
            return True
        if payment.order.payment_type == Order.PaymentTypeChoices.FULL:
            return True
        return payment.order.installments.filter(
            status=PaymentInstallment.StatusChoices.PAID,
        ).exists()

    @classmethod
    @transaction.atomic
    def handle_checkout_session_completed(cls, session: dict) -> Payment:
        payment = Payment.objects.select_for_update().get(
            stripe_session_id=session["id"],
        )

        if session.get("payment_status") not in {"paid", "no_payment_required"}:
            raise PaymentError("Checkout session is not paid.")

        return cls._complete_successful_payment(
            payment,
            payment_intent_id=session.get("payment_intent") or "",
            customer_id=session.get("customer") or "",
            attempt_metadata={"stripe_session_id": session["id"]},
        )

    @classmethod
    @transaction.atomic
    def handle_payment_intent_succeeded(cls, payment_intent: dict) -> Payment | None:
        metadata = payment_intent.get("metadata") or {}
        payment = None

        payment_id = metadata.get("payment_id")
        if payment_id:
            payment = Payment.objects.select_for_update().filter(pk=payment_id).first()

        if payment is None:
            payment = (
                Payment.objects.select_for_update()
                .filter(
                    stripe_payment_intent_id=payment_intent["id"],
                )
                .first()
            )

        if payment is None:
            return None

        if payment_intent.get("status") != "succeeded":
            raise PaymentError("PaymentIntent is not succeeded.")

        return cls._complete_successful_payment(
            payment,
            payment_intent_id=payment_intent["id"],
            customer_id=payment_intent.get("customer") or "",
            attempt_metadata={"stripe_payment_intent_id": payment_intent["id"]},
            charge_id=payment_intent.get("latest_charge") or "",
        )

    @staticmethod
    def handle_payment_intent_failed(payment_intent: dict) -> None:
        metadata = payment_intent.get("metadata") or {}
        payment_id = metadata.get("payment_id")
        payment = None

        if payment_id:
            payment = Payment.objects.select_related("installment").filter(pk=payment_id).first()

        if payment is None:
            payment = (
                Payment.objects.select_related("installment")
                .filter(
                    stripe_payment_intent_id=payment_intent["id"],
                )
                .first()
            )

        if payment and payment.status != Payment.StatusChoices.SUCCEEDED:
            payment.mark_as_failed("Stripe PaymentIntent failed.")
            if payment.installment_id:
                payment.installment.mark_as_failed()
            PaymentAttempt.objects.create(
                payment=payment,
                status=Payment.StatusChoices.FAILED,
                error_message="Stripe PaymentIntent failed.",
                metadata={"stripe_payment_intent_id": payment_intent["id"]},
            )

    @classmethod
    def _validate_payment_intent_matches_payment(
        cls,
        *,
        payment: Payment,
        payment_intent: dict,
    ) -> None:
        if payment_intent.get("id") != payment.stripe_payment_intent_id:
            raise PaymentError("Stripe PaymentIntent id does not match this payment.")

        metadata = payment_intent.get("metadata") or {}
        if str(metadata.get("payment_id") or "") != str(payment.id):
            raise PaymentError("Stripe PaymentIntent metadata does not match this payment.")

        if payment_intent.get("amount") != cls._to_minor_units(payment.amount):
            raise PaymentError("Stripe PaymentIntent amount does not match this payment.")

        if str(payment_intent.get("currency") or "").lower() != payment.currency.lower():
            raise PaymentError("Stripe PaymentIntent currency does not match this payment.")

    @classmethod
    @transaction.atomic
    def sync_payment_intent_status(
        cls,
        *,
        user,
        payment_id: int,
        payment_intent_id: str,
    ) -> tuple[Payment, str]:
        payment = (
            Payment.objects.select_for_update(of=("self",))
            .select_related("order", "installment")
            .filter(
                pk=payment_id,
                user=user,
                stripe_payment_intent_id=payment_intent_id,
            )
            .first()
        )
        if payment is None:
            raise PaymentError("PaymentIntent was not found for this user.")

        payment_intent = cls.serialize_stripe_object(
            cls._retrieve_stripe_payment_intent(payment_intent_id)
        )
        cls._validate_payment_intent_matches_payment(
            payment=payment,
            payment_intent=payment_intent,
        )

        stripe_status = payment_intent.get("status") or ""
        if stripe_status == "succeeded":
            payment = cls._complete_successful_payment(
                payment,
                payment_intent_id=payment_intent["id"],
                customer_id=payment_intent.get("customer") or "",
                attempt_metadata={
                    "stripe_payment_intent_id": payment_intent["id"],
                    "source": "payment_intent_status_sync",
                },
            )
        elif stripe_status in {"requires_payment_method", "canceled"}:
            cls.handle_payment_intent_failed(payment_intent)
            payment.refresh_from_db()

        return payment, stripe_status

    @staticmethod
    def handle_checkout_session_expired(session: dict) -> None:
        payment = (
            Payment.objects.select_related("installment")
            .filter(
                stripe_session_id=session["id"],
            )
            .first()
        )
        if payment and payment.status in {
            Payment.StatusChoices.PENDING,
            Payment.StatusChoices.PROCESSING,
        }:
            payment.mark_as_canceled("Stripe Checkout session expired.")
            if payment.installment_id:
                payment.installment.mark_as_pending()

    @staticmethod
    def handle_checkout_session_failed(session: dict) -> None:
        payment = (
            Payment.objects.select_related("installment")
            .filter(
                stripe_session_id=session["id"],
            )
            .first()
        )
        if payment and payment.status != Payment.StatusChoices.SUCCEEDED:
            payment.mark_as_failed("Stripe Checkout payment failed.")
            if payment.installment_id:
                payment.installment.mark_as_failed()
            PaymentAttempt.objects.create(
                payment=payment,
                status=Payment.StatusChoices.FAILED,
                error_message="Stripe Checkout payment failed.",
                metadata={"stripe_session_id": session["id"]},
            )

    @staticmethod
    def _grant_enrollments(payment: Payment) -> None:
        order = payment.order if payment.order_id else None
        items = (
            order.items.select_related(
                "course", "cohort", "pricing_plan__delivery_format"
            ).prefetch_related("schedule_slots")
            if order is not None
            else payment.items.select_related(
                "course", "cohort", "pricing_plan__delivery_format"
            ).prefetch_related("schedule_slots")
        )
        access_order_id = order.id if order is not None else payment.id

        for item in items:
            if item.course is None:
                continue
            delivery_format = (
                item.pricing_plan.delivery_format
                if item.pricing_plan_id and item.pricing_plan
                else None
            )
            enrollment, created = Enrollment.objects.get_or_create(
                student_profile=payment.student_profile,
                course=item.course,
                defaults={
                    "order_id": access_order_id,
                    "access_status": Enrollment.AccessStatusChoices.ACTIVE,
                    "delivery_format": delivery_format,
                },
            )
            if not created and enrollment.delivery_format_id is None and delivery_format:
                enrollment.delivery_format = delivery_format
                enrollment.save(update_fields=["delivery_format"])
            if not created and enrollment.access_status != Enrollment.AccessStatusChoices.ACTIVE:
                enrollment.access_status = Enrollment.AccessStatusChoices.ACTIVE
                enrollment.order_id = access_order_id
                enrollment.access_until = None
                enrollment.access_granted_at = timezone.now()
                enrollment.save(
                    update_fields=[
                        "access_status",
                        "order_id",
                        "access_until",
                        "access_granted_at",
                    ]
                )

            EnrollmentService.apply_delivery_setup(
                enrollment,
                cohort_id=item.cohort_id,
                schedule_slot_ids=list(item.schedule_slots.values_list("id", flat=True)),
            )

    @staticmethod
    def _remove_paid_items_from_cart(payment: Payment) -> None:
        order = payment.order if payment.order_id else None
        items = order.items.all() if order is not None else payment.items.all()
        course_ids = [item.course_id for item in items if item.course_id is not None]
        if not course_ids:
            return
        CartItem.objects.filter(
            cart__student_profile=payment.student_profile,
            course_id__in=course_ids,
        ).delete()
