from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payments.views import (
    OrderViewSet,
    PaymentViewSet,
    StripeWebhookView,
    TeacherOrderInvoiceView,
    TeacherOrdersView,
)

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"payments", PaymentViewSet, basename="payments")

urlpatterns = [
    # Must precede the router include: the router's detail route
    # (`orders/<pk>/`) would otherwise swallow `orders/teacher/` by treating
    # "teacher" as a pk.
    path("orders/teacher/", TeacherOrdersView.as_view(), name="teacher-orders"),
    path(
        "orders/teacher/<int:order_id>/invoice/",
        TeacherOrderInvoiceView.as_view(),
        name="teacher-order-invoice",
    ),
    path("", include(router.urls)),
    path("payments/stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
]
