from .checkout import CheckoutService
from .invoice import InvoiceService
from .liqpay import LiqPayService
from .payout_execution import PayoutExecutionService
from .payouts import PayoutService
from .refunds import RefundService
from .stripe import StripeService
from .summary import SummaryService
from .teacher_finance import TeacherFinanceService
from .webhooks import WebhookService


class PaymentService(
    CheckoutService,
    InvoiceService,
    RefundService,
    PayoutService,
    SummaryService,
    WebhookService,
    StripeService,
    LiqPayService,
    TeacherFinanceService,
    PayoutExecutionService,
):
    pass
