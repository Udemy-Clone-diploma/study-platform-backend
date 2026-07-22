from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.payments.models import Payment
from apps.users.models import User

from .base import PaymentBaseService
from .exceptions import PaymentError


class StripeService(PaymentBaseService):
    @staticmethod
    def _load_stripe():
        try:
            import stripe
        except ImportError as exc:
            raise ImproperlyConfigured("Install the stripe package to use Stripe payments.") from exc

        secret_key = getattr(settings, "STRIPE_SECRET_KEY", "")
        if not secret_key:
            raise ImproperlyConfigured("STRIPE_SECRET_KEY is not configured.")

        stripe.api_key = secret_key
        return stripe

    @staticmethod
    def _stripe_payment_metadata(payment: Payment, user: User) -> dict[str, str]:
        return {
            "payment_id": str(payment.id),
            "order_id": str(payment.order_id or ""),
            "installment_id": str(payment.installment_id or ""),
            "payment_type": payment.order.payment_type if payment.order_id else "",
            "user_id": str(user.id),
        }

    @classmethod
    def _create_stripe_session(
        cls,
        *,
        payment: Payment,
        user: User,
        line_items: list[dict],
        success_url: str,
        cancel_url: str,
    ):
        stripe = cls._load_stripe()
        metadata = cls._stripe_payment_metadata(payment, user)
        return stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user.email,
            client_reference_id=str(payment.id),
            metadata=metadata,
            payment_intent_data={"metadata": metadata},
        )

    @classmethod
    def _create_stripe_payment_intent(cls, *, payment: Payment, user: User):
        stripe = cls._load_stripe()
        metadata = cls._stripe_payment_metadata(payment, user)
        return stripe.PaymentIntent.create(
            amount=cls._to_minor_units(payment.amount),
            currency=payment.currency.lower(),
            description=payment.description or f"Payment #{payment.id}",
            metadata=metadata,
            payment_method_types=["card"],
            receipt_email=user.email,
        )

    @classmethod
    def _create_stripe_refund(cls, *, payment: Payment, amount, reason: str):
        stripe = cls._load_stripe()
        return stripe.Refund.create(
            payment_intent=payment.stripe_payment_intent_id,
            amount=cls._to_minor_units(amount),
            # Stripe's own `reason` accepts only its three fixed codes, so the
            # administrator's free text rides along as metadata instead.
            metadata={"payment_id": str(payment.id), "reason": reason},
        )

    @classmethod
    def _retrieve_stripe_payment_intent(cls, payment_intent_id: str):
        stripe = cls._load_stripe()
        return stripe.PaymentIntent.retrieve(payment_intent_id)

    @classmethod
    def _retrieve_stripe_payment_intent_client_secret(cls, payment_intent_id: str) -> str:
        payment_intent = cls._retrieve_stripe_payment_intent(payment_intent_id)
        client_secret = getattr(payment_intent, "client_secret", "")
        if not client_secret:
            raise PaymentError("Stripe payment intent client secret is unavailable.")
        return client_secret

    @staticmethod
    def serialize_stripe_object(value):
        to_dict_recursive = getattr(value, "to_dict_recursive", None)
        if callable(to_dict_recursive):
            return to_dict_recursive()
        private_to_dict_recursive = getattr(value, "_to_dict_recursive", None)
        if callable(private_to_dict_recursive):
            return private_to_dict_recursive()
        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            return to_dict()
        if isinstance(value, dict):
            return value
        raise PaymentError("Unsupported Stripe event payload.")

    @classmethod
    def construct_stripe_event(cls, payload: bytes, signature: str | None):
        stripe = cls._load_stripe()
        webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        if not webhook_secret:
            raise ImproperlyConfigured("STRIPE_WEBHOOK_SECRET is not configured.")
        return stripe.Webhook.construct_event(payload, signature, webhook_secret)
