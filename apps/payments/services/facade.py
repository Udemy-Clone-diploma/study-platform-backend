from .checkout import CheckoutService
from .invoice import InvoiceService
from .refunds import RefundService
from .payouts import PayoutService
from .stripe import StripeService
from .summary import SummaryService
from .webhooks import WebhookService
from .liqpay import LiqPayService
from .teacher_finance import TeacherFinanceService
from .payout_execution import PayoutExecutionService

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
