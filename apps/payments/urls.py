from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payments.views import (
    OrderViewSet,
    PaymentViewSet,
    StripeWebhookView,
    TeacherOrderInvoiceView,
    TeacherOrdersView,
    TeacherPayoutStatusView,
    TeacherPayoutOnboardingView,
    TeacherPayoutRefreshView,
    LiqPayCallbackView,
    TeacherFinanceBalanceView,
    TeacherFinanceLedgerView,
    TeacherStripeFinanceView,
    TeacherFinancePayoutHistoryView,
    TeacherPayoutDestinationViewSet,
    StaffTeacherPayoutViewSet,
    StaffTeacherBalanceView,
    LiqPayPayoutCallbackView,
)

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"payments", PaymentViewSet, basename="payments")
router.register(
    r"teacher/finance/destinations",
    TeacherPayoutDestinationViewSet,
    basename="teacher-finance-destinations",
)
router.register(
    r"staff/finance/payouts",
    StaffTeacherPayoutViewSet,
    basename="staff-finance-payouts",
)

urlpatterns = [
    path("teacher/payouts/", TeacherPayoutStatusView.as_view(), name="teacher-payout-status"),
    path(
        "teacher/payouts/finance/",
        TeacherStripeFinanceView.as_view(),
        name="teacher-stripe-finance",
    ),
    path("teacher/payouts/onboarding/", TeacherPayoutOnboardingView.as_view(), name="teacher-payout-onboarding"),
    path("teacher/payouts/refresh/", TeacherPayoutRefreshView.as_view(), name="teacher-payout-refresh"),
    # Must precede the router include: the router's detail route
    # (`orders/<pk>/`) would otherwise swallow `orders/teacher/` by treating
    # "teacher" as a pk.
    path("orders/teacher/", TeacherOrdersView.as_view(), name="teacher-orders"),
    path(
        "orders/teacher/<int:order_id>/invoice/",
        TeacherOrderInvoiceView.as_view(),
        name="teacher-order-invoice",
    ),
    path("payments/stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("payments/liqpay/callback/", LiqPayCallbackView.as_view(), name="liqpay-callback"),
    path(
        "payments/liqpay/payout/callback/",
        LiqPayPayoutCallbackView.as_view(),
        name="liqpay-payout-callback",
    ),
    path(
        "teacher/finance/balance/",
        TeacherFinanceBalanceView.as_view(),
        name="teacher-finance-balance",
    ),
    path(
        "teacher/finance/ledger/",
        TeacherFinanceLedgerView.as_view(),
        name="teacher-finance-ledger",
    ),
    path(
        "teacher/finance/payouts/",
        TeacherFinancePayoutHistoryView.as_view(),
        name="teacher-finance-payouts",
    ),
    path(
        "staff/finance/teachers/"
        "<int:teacher_id>/balance/",
        StaffTeacherBalanceView.as_view(),
        name="staff-teacher-finance-balance",
    ),
    path("", include(router.urls)),
]
