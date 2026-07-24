from .checkout import CheckoutService
from .invoice import InvoiceService
from .refunds import RefundService
from .stripe import StripeService
from .summary import SummaryService
from .webhooks import WebhookService


class PaymentService(
    CheckoutService,
    InvoiceService,
    RefundService,
    SummaryService,
    WebhookService,
    StripeService,
):
    pass
