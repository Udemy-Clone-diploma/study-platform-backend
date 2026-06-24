from django.db import transaction
from django.utils import timezone

from apps.cart.models import CartItem
from apps.courses.models import CohortMember
from apps.enrollments.models import Enrollment
from apps.payments.models import (
    Order,
    Payment,
    PaymentAttempt,
    PaymentInstallment,
    WebhookEvent,
)

from .base import PaymentBaseService
from .exceptions import PaymentError


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
    ) -> Payment:
        if payment.status == Payment.StatusChoices.SUCCEEDED:
            return payment

        payment.mark_as_succeeded(
            payment_intent_id=payment_intent_id,
            customer_id=customer_id,
        )

        if payment.installment_id:
            payment.installment.mark_as_paid()

        if payment.order_id:
            payment.order.sync_status_from_payments()

        if cls._payment_should_grant_access(payment):
            cls._grant_enrollments(payment)
            cls._remove_paid_items_from_cart(payment)

        PaymentAttempt.objects.get_or_create(
            payment=payment,
            status=Payment.StatusChoices.SUCCEEDED,
            defaults={"metadata": attempt_metadata or {}},
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
            payment = Payment.objects.select_for_update().filter(
                stripe_payment_intent_id=payment_intent["id"],
            ).first()

        if payment is None:
            return None

        if payment_intent.get("status") != "succeeded":
            raise PaymentError("PaymentIntent is not succeeded.")

        return cls._complete_successful_payment(
            payment,
            payment_intent_id=payment_intent["id"],
            customer_id=payment_intent.get("customer") or "",
            attempt_metadata={"stripe_payment_intent_id": payment_intent["id"]},
        )

    @staticmethod
    def handle_payment_intent_failed(payment_intent: dict) -> None:
        metadata = payment_intent.get("metadata") or {}
        payment_id = metadata.get("payment_id")
        payment = None

        if payment_id:
            payment = Payment.objects.select_related("installment").filter(pk=payment_id).first()

        if payment is None:
            payment = Payment.objects.select_related("installment").filter(
                stripe_payment_intent_id=payment_intent["id"],
            ).first()

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
        payment = Payment.objects.select_related("installment").filter(
            stripe_session_id=session["id"],
        ).first()
        if payment and payment.status in {
            Payment.StatusChoices.PENDING,
            Payment.StatusChoices.PROCESSING,
        }:
            payment.mark_as_canceled("Stripe Checkout session expired.")
            if payment.installment_id:
                payment.installment.mark_as_pending()

    @staticmethod
    def handle_checkout_session_failed(session: dict) -> None:
        payment = Payment.objects.select_related("installment").filter(
            stripe_session_id=session["id"],
        ).first()
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
            order.items.select_related("course", "cohort", "pricing_plan__delivery_format")
            if order is not None
            else payment.items.select_related("course", "cohort", "pricing_plan__delivery_format")
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

            if item.cohort_id:
                CohortMember.objects.get_or_create(
                    cohort_id=item.cohort_id,
                    enrollment=enrollment,
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
