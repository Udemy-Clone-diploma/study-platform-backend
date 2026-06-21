import logging

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.models import Order, Payment
from apps.payments.serializers import (
    CheckoutSessionCreateSerializer,
    CheckoutSessionSerializer,
    OrderSerializer,
    PaymentIntentCreateSerializer,
    PaymentIntentSerializer,
    PaymentIntentStatusSerializer,
    PaymentIntentStatusSyncSerializer,
    PaymentSerializer,
)
from apps.payments.services import PaymentError, PaymentService
from apps.users.models import User
from apps.users.permissions import IsStudent

logger = logging.getLogger(__name__)


@extend_schema(tags=["Payments"])
class PaymentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = (
            Payment.objects.select_related(
                "user",
                "student_profile__user",
                "order",
                "installment",
            )
            .prefetch_related(
                "items",
                "items__course",
                "items__pricing_plan",
                "order__items",
                "order__items__course",
                "order__items__pricing_plan",
                "order__installments",
            )
        )
        user = self.request.user
        if user.role == User.RoleChoices.ADMINISTRATOR:
            return queryset
        return queryset.filter(user=user)

    def get_permissions(self):
        if self.action in {
            "create_checkout_session",
            "create_payment_intent",
            "sync_payment_intent_status",
        }:
            return [IsStudent()]
        return super().get_permissions()

    @extend_schema(summary="Download a receipt PDF for a successful payment")
    @action(detail=True, methods=["get"], url_path="receipt")
    def receipt(self, request, *args, **kwargs):
        payment = self.get_object()
        try:
            pdf = PaymentService.generate_payment_receipt_pdf(payment)
        except PaymentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        filename_id = payment.order_id or payment.id
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="receipt-{filename_id}-{payment.id}.pdf"'
        )
        response["Content-Length"] = str(len(pdf))
        return response

    @extend_schema(
        request=CheckoutSessionCreateSerializer,
        responses={201: CheckoutSessionSerializer},
        summary="Create a Stripe Checkout Session for the current student's cart",
    )
    @action(detail=False, methods=["post"], url_path="checkout-session")
    def create_checkout_session(self, request, *args, **kwargs):
        serializer = CheckoutSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = PaymentService.create_checkout_session(
                user=request.user,
                success_url=serializer.validated_data.get("success_url"),
                cancel_url=serializer.validated_data.get("cancel_url"),
                selected_cart_item_ids=serializer.validated_data.get("selected_cart_item_ids"),
                payment_type=serializer.validated_data.get("payment_type"),
                installments_count=serializer.validated_data.get("installments_count"),
            )
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except PaymentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            return Response(
                {"detail": "Could not create Stripe checkout session."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "checkout_url": payment.checkout_url,
                "session_id": payment.stripe_session_id,
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "installment_id": payment.installment_id,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=PaymentIntentCreateSerializer,
        responses={201: PaymentIntentSerializer},
        summary="Create a Stripe PaymentIntent for the current student's cart",
    )
    @action(detail=False, methods=["post"], url_path="payment-intent")
    def create_payment_intent(self, request, *args, **kwargs):
        serializer = PaymentIntentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment, client_secret = PaymentService.create_payment_intent(
                user=request.user,
                selected_cart_item_ids=serializer.validated_data.get("selected_cart_item_ids"),
                payment_type=serializer.validated_data.get("payment_type"),
                installments_count=serializer.validated_data.get("installments_count"),
            )
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except PaymentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            return Response(
                {"detail": "Could not create Stripe payment intent."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "client_secret": client_secret,
                "payment_intent_id": payment.stripe_payment_intent_id,
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "installment_id": payment.installment_id,
                "amount": f"{payment.amount:.2f}",
                "currency": payment.currency,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=PaymentIntentStatusSyncSerializer,
        responses={200: PaymentIntentStatusSerializer},
        summary="Sync a Stripe PaymentIntent status for the current student's payment",
    )
    @action(detail=False, methods=["post"], url_path="payment-intent/sync")
    def sync_payment_intent_status(self, request, *args, **kwargs):
        serializer = PaymentIntentStatusSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment, stripe_status = PaymentService.sync_payment_intent_status(
                user=request.user,
                payment_id=serializer.validated_data["payment_id"],
                payment_intent_id=serializer.validated_data["payment_intent_id"],
            )
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except PaymentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            logger.exception("Could not sync Stripe payment intent status.")
            return Response(
                {"detail": "Could not sync Stripe payment intent status."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "installment_id": payment.installment_id,
                "payment_status": payment.status,
                "order_status": payment.order.status if payment.order_id else None,
                "stripe_payment_intent_status": stripe_status,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Orders"])
class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = (
            Order.objects.select_related("user", "student_profile__user")
            .prefetch_related(
                "items",
                "items__course",
                "items__pricing_plan",
                "installments",
                "payments",
            )
        )
        user = self.request.user
        if user.role == User.RoleChoices.ADMINISTRATOR:
            return queryset
        return queryset.filter(user=user)

    def get_permissions(self):
        if self.action in {
            "create_installment_checkout_session",
            "create_installment_payment_intent",
        }:
            return [IsStudent()]
        return super().get_permissions()

    @extend_schema(summary="Download an order invoice as a PDF")
    @action(detail=True, methods=["get"], url_path="invoice")
    def invoice(self, request, *args, **kwargs):
        order = self.get_object()
        pdf = PaymentService.generate_order_invoice_pdf(order)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="invoice-{order.id}.pdf"'
        response["Content-Length"] = str(len(pdf))
        return response

    @extend_schema(
        request=CheckoutSessionCreateSerializer,
        responses={201: CheckoutSessionSerializer},
        summary="Create a Stripe Checkout Session for an order installment",
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"installments/(?P<installment_id>\d+)/checkout-session",
    )
    def create_installment_checkout_session(self, request, installment_id=None, *args, **kwargs):
        serializer = CheckoutSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = PaymentService.create_installment_checkout_session(
                user=request.user,
                order_id=self.get_object().id,
                installment_id=int(installment_id),
                success_url=serializer.validated_data.get("success_url"),
                cancel_url=serializer.validated_data.get("cancel_url"),
            )
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except PaymentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            return Response(
                {"detail": "Could not create Stripe checkout session."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "checkout_url": payment.checkout_url,
                "session_id": payment.stripe_session_id,
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "installment_id": payment.installment_id,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=None,
        responses={201: PaymentIntentSerializer},
        summary="Create a Stripe PaymentIntent for an order installment",
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"installments/(?P<installment_id>\d+)/payment-intent",
    )
    def create_installment_payment_intent(self, request, installment_id=None, *args, **kwargs):
        try:
            payment, client_secret = PaymentService.create_installment_payment_intent(
                user=request.user,
                order_id=self.get_object().id,
                installment_id=int(installment_id),
            )
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except PaymentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            return Response(
                {"detail": "Could not create Stripe payment intent."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "client_secret": client_secret,
                "payment_intent_id": payment.stripe_payment_intent_id,
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "installment_id": payment.installment_id,
                "amount": f"{payment.amount:.2f}",
                "currency": payment.currency,
            },
            status=status.HTTP_201_CREATED,
        )

@extend_schema(tags=["Payments"])
class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def post(self, request, *args, **kwargs):
        signature = request.headers.get("Stripe-Signature")

        try:
            event = PaymentService.construct_stripe_event(request.body, signature)
        except ValueError:
            return Response({"detail": "Invalid payload."}, status=status.HTTP_400_BAD_REQUEST)
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        event_data = PaymentService.serialize_stripe_object(event)
        webhook_event, created = PaymentService.record_stripe_event(event_data)

        if not created and webhook_event.status in {
            webhook_event.StatusChoices.PROCESSED,
            webhook_event.StatusChoices.IGNORED,
        }:
            return Response({"received": True})

        try:
            PaymentService.process_webhook_event(webhook_event)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"received": True})
