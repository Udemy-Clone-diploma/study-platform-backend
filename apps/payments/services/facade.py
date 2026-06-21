from .checkout import CheckoutService
from .invoice import InvoiceService
from .stripe import StripeService
from .webhooks import WebhookService


class PaymentService(CheckoutService, InvoiceService, WebhookService, StripeService):
    pass
