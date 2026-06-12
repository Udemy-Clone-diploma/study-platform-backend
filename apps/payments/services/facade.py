from .checkout import CheckoutService
from .stripe import StripeService
from .webhooks import WebhookService


class PaymentService(CheckoutService, WebhookService, StripeService):
    pass
