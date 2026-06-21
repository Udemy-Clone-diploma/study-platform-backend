from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.payments.views import OrderViewSet, PaymentViewSet, StripeWebhookView

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"payments", PaymentViewSet, basename="payments")

urlpatterns = [
    path("", include(router.urls)),
    path("payments/stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
]
