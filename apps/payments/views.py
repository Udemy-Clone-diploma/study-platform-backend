import logging

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.files import absolute_media_url
from apps.courses.models import Cohort, Course
from apps.payments.filters import PaymentFilter
from apps.payments.models import Order, Payment, PaymentInstallment
from apps.payments.serializers import (
    CheckoutSessionCreateSerializer,
    CheckoutSessionSerializer,
    OrderSerializer,
    PaymentIntentCreateSerializer,
    PaymentIntentSerializer,
    PaymentIntentStatusSerializer,
    PaymentCategoryRevenueSerializer,
    PaymentIntentStatusSyncSerializer,
    PaymentSerializer,
    PaymentSummarySerializer,
    PaymentTimeseriesPointSerializer,
    RefundCreateSerializer,
)
from apps.payments.services import PaymentError, PaymentService, RefundError
from apps.users.models import User
from apps.users.permissions import IsAdmin, IsStudent

logger = logging.getLogger(__name__)


def _derive_order_status(order: Order) -> str:
    """Paid/unpaid/overdue for the teacher Payments table, derived from order
    status plus (for installment orders) whether any installment is past due."""
    if order.status == Order.StatusChoices.PAID:
        return "paid"
    if order.payment_type == Order.PaymentTypeChoices.INSTALLMENTS:
        overdue = order.installments.filter(
            status=PaymentInstallment.StatusChoices.PENDING,
            due_date__lt=timezone.now().date(),
        ).exists()
        if overdue:
            return "overdue"
    return "unpaid"


@extend_schema(tags=["Payments"])
class PaymentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = PaymentFilter
    ordering_fields = ["created_at", "amount", "status"]
    ordering = ["-created_at"]

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
                "refunds",
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
        if self.action in {"summary", "timeseries", "revenue_by_category", "refund"}:
            return [IsAdmin()]
        return super().get_permissions()

    @extend_schema(
        responses={200: PaymentSummarySerializer},
        summary="Aggregated payment totals for the admin Finance panel",
    )
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request, *args, **kwargs):
        summary = PaymentService.payment_summary(self.filter_queryset(self.get_queryset()))
        summary["previous"] = self._previous_summary(request)
        return Response(PaymentSummarySerializer(summary).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "group_by",
                str,
                description="Bucket size: day (default), week or month.",
            )
        ],
        responses={200: PaymentTimeseriesPointSerializer(many=True)},
        summary="Gross revenue over time for the admin Finance panel chart",
    )
    @action(detail=False, methods=["get"], url_path="summary/timeseries")
    def timeseries(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        date_from, date_to = self._requested_window(request)
        try:
            points = PaymentService.payment_timeseries(
                queryset,
                request.query_params.get("group_by", "day"),
                date_from=date_from,
                date_to=date_to,
            )
        except PaymentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PaymentTimeseriesPointSerializer(points, many=True).data)

    @extend_schema(
        responses={200: PaymentCategoryRevenueSerializer(many=True)},
        summary="Gross revenue split by course category, for the admin Finance donut",
    )
    @action(detail=False, methods=["get"], url_path="revenue-by-category")
    def revenue_by_category(self, request, *args, **kwargs):
        rows = PaymentService.revenue_by_category(
            self.filter_queryset(self.get_queryset())
        )
        return Response(PaymentCategoryRevenueSerializer(rows, many=True).data)

    def _requested_window(self, request):
        """The date range the caller asked for. Already validated by
        PaymentFilter, which 400s on a malformed date before this runs."""
        return (
            parse_date(request.query_params.get("date_from") or ""),
            parse_date(request.query_params.get("date_to") or ""),
        )

    def _previous_summary(self, request):
        date_from, date_to = self._requested_window(request)
        if not date_from or not date_to:
            return None

        previous_from, previous_to = PaymentService.previous_window(date_from, date_to)
        # Re-run the same filters with only the window swapped, so the
        # comparison differs from the current period in nothing else.
        params = request.query_params.copy()
        params["date_from"] = previous_from.isoformat()
        params["date_to"] = previous_to.isoformat()
        queryset = PaymentFilter(params, queryset=self.get_queryset(), request=request).qs

        return {
            "date_from": previous_from,
            "date_to": previous_to,
            **PaymentService.payment_summary(queryset),
        }

    @extend_schema(
        request=RefundCreateSerializer,
        responses={200: PaymentSerializer},
        summary="Refund a payment through Stripe (administrators only)",
    )
    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, *args, **kwargs):
        payment = self.get_object()
        serializer = RefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            PaymentService.refund_payment(
                payment=payment,
                amount=serializer.validated_data.get("amount"),
                reason=serializer.validated_data["reason"],
                created_by=request.user,
            )
        except RefundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            logger.exception("Could not refund payment %s.", payment.id)
            return Response(
                {"detail": "Could not refund the payment through Stripe."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Re-read so the response carries a fresh `refunds` prefetch, which the
        # instance from get_object() cached before the new row existed.
        refunded = self.get_queryset().get(pk=payment.pk)
        return Response(self.get_serializer(refunded).data)

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


@extend_schema(tags=["Orders"])
class TeacherOrdersView(APIView):
    """GET /orders/teacher/ -- one row per (student, course) purchase across
    the teacher's own courses, for the teacher dashboard Payments table."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role != User.RoleChoices.TEACHER:
            return Response({"results": [], "courses": [], "cohorts": []})
        teacher_profile = user.teacher_profile

        course_slug = request.query_params.get("course")
        cohort_id = request.query_params.get("cohort")
        status_param = request.query_params.get("status")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        search = request.query_params.get("search")

        orders = (
            Order.objects.filter(items__course__teacher_profile=teacher_profile)
            .distinct()
            .select_related("student_profile__user")
            .prefetch_related("items__course", "items__cohort", "installments")
        )
        if course_slug:
            orders = orders.filter(items__course__slug=course_slug)
        if cohort_id:
            orders = orders.filter(items__cohort_id=cohort_id)
        if date_from:
            orders = orders.filter(created_at__date__gte=date_from)
        if date_to:
            orders = orders.filter(created_at__date__lte=date_to)
        if search:
            orders = orders.filter(
                Q(student_profile__user__first_name__icontains=search)
                | Q(student_profile__user__last_name__icontains=search)
                | Q(student_profile__user__email__icontains=search)
            )

        rows = []
        for order in orders.order_by("-created_at"):
            row_status = _derive_order_status(order)
            if status_param and row_status != status_param:
                continue
            # Installments are prefetched ordered by due_date (see PaymentInstallment.Meta),
            # so the first still-pending one is the next payment the student owes.
            next_due = next(
                (i.due_date for i in order.installments.all() if i.status == PaymentInstallment.StatusChoices.PENDING),
                None,
            )
            for item in order.items.all():
                if not item.course_id or item.course.teacher_profile_id != teacher_profile.id:
                    continue
                if course_slug and item.course.slug != course_slug:
                    continue
                if cohort_id and str(item.cohort_id) != cohort_id:
                    continue
                cohort_name = None
                if item.cohort_id:
                    cohort_name = item.cohort.name or f"Group {item.cohort_id}"
                rows.append({
                    "order_id": order.id,
                    "student_id": order.student_profile_id,
                    "student_name": order.student_profile.user.get_full_name(),
                    "student_avatar": absolute_media_url(order.student_profile.user.avatar, request),
                    "course_slug": item.course.slug,
                    "course_title": item.course_title,
                    "cohort_id": item.cohort_id,
                    "cohort_name": cohort_name,
                    "payment_plan": order.get_payment_type_display(),
                    "status": row_status,
                    "amount": str(item.unit_amount),
                    "currency": item.currency,
                    "date": (order.completed_at or order.created_at).isoformat(),
                    "due_date": next_due.isoformat() if next_due else None,
                    "has_receipt": row_status == "paid",
                })

        courses = Course.objects.filter(teacher_profile=teacher_profile)
        cohorts_qs = (
            Cohort.objects.filter(course__teacher_profile=teacher_profile, course__slug=course_slug)
            if course_slug
            else Cohort.objects.none()
        )

        return Response({
            "results": rows,
            "courses": [{"slug": c.slug, "title": c.title} for c in courses],
            "cohorts": [{"id": c.id, "name": c.name or f"Group {c.id}"} for c in cohorts_qs],
        })


@extend_schema(tags=["Orders"])
class TeacherOrderInvoiceView(APIView):
    """GET /orders/teacher/<order_id>/invoice/ -- download the invoice PDF for
    an order that includes one of the requesting teacher's courses."""

    permission_classes = [IsAuthenticated]

    def get(self, request, order_id, *args, **kwargs):
        user = request.user
        if user.role != User.RoleChoices.TEACHER:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        order = get_object_or_404(
            Order.objects.filter(items__course__teacher_profile=user.teacher_profile).distinct(),
            pk=order_id,
        )
        pdf = PaymentService.generate_order_invoice_pdf(order)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="invoice-{order.id}.pdf"'
        response["Content-Length"] = str(len(pdf))
        return response


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
