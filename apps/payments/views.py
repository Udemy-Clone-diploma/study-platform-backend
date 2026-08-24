import logging

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.files import absolute_media_url
from apps.courses.models import Cohort, Course
from apps.payments.filters import PaymentFilter
from apps.payments.models import (
    Order,
    Payment,
    PaymentInstallment,
    Refund,
    TeacherLedgerEntry,
    TeacherPayout,
    TeacherPayoutAccount,
    TeacherPayoutDestination,
)
from apps.payments.permissions import IsFinanceOperator
from apps.payments.serializers import (
    CheckoutSessionCreateSerializer,
    CheckoutSessionSerializer,
    LiqPayCheckoutCreateSerializer,
    LiqPayCheckoutSerializer,
    LiqPayStatusSerializer,
    LiqPayStatusSyncSerializer,
    OrderSerializer,
    PaymentCategoryRevenueSerializer,
    PaymentIntentCreateSerializer,
    PaymentIntentSerializer,
    PaymentIntentStatusSerializer,
    PaymentIntentStatusSyncSerializer,
    PaymentSerializer,
    PaymentSummarySerializer,
    PaymentTimeseriesPointSerializer,
    RefundCreateSerializer,
    StaffPayoutCreateSerializer,
    StaffTeacherPayoutSerializer,
    TeacherBalanceSerializer,
    TeacherLedgerEntrySerializer,
    TeacherPayoutDestinationSerializer,
    TeacherPayoutSerializer,
)
from apps.payments.services import PaymentError, PaymentService, RefundError
from apps.users.models import TeacherProfile, User
from apps.users.permissions import IsAdmin, IsStudent, IsTeacher

logger = logging.getLogger(__name__)

TEACHER_FINANCE_CURRENCY = "USD"


def _teacher_finance_currency(
    request,
    *,
    default: str = "",
) -> str:
    currency = (
        str(
            request.query_params.get(
                "currency",
                default,
            )
            or ""
        )
        .strip()
        .upper()
    )

    if currency and currency != TEACHER_FINANCE_CURRENCY:
        raise ValidationError({"currency": ("Unsupported currency.")})

    return currency


@extend_schema(tags=["Teacher finance"])
class TeacherPayoutDestinationViewSet(viewsets.ModelViewSet):
    permission_classes = [
        IsAuthenticated,
        IsTeacher,
    ]

    serializer_class = TeacherPayoutDestinationSerializer

    http_method_names = [
        "get",
        "post",
        "patch",
        "delete",
        "head",
        "options",
    ]

    def get_queryset(self):
        return TeacherPayoutDestination.objects.filter(
            teacher=(self.request.user.teacher_profile)
        ).order_by(
            "-is_default",
            "-created_at",
        )

    def perform_destroy(
        self,
        instance,
    ):
        with transaction.atomic():
            instance = TeacherPayoutDestination.objects.select_for_update().get(pk=instance.pk)

            was_default = instance.is_default

            instance.is_active = False
            instance.is_default = False

            instance.save(
                update_fields=[
                    "is_active",
                    "is_default",
                    "updated_at",
                ]
            )

            if not was_default:
                return

            replacement = (
                TeacherPayoutDestination.objects.select_for_update()
                .filter(
                    teacher=instance.teacher,
                    provider=instance.provider,
                    is_active=True,
                )
                .exclude(pk=instance.pk)
                .order_by("-created_at")
                .first()
            )

            if replacement:
                replacement.is_default = True

                replacement.save(
                    update_fields=[
                        "is_default",
                        "updated_at",
                    ]
                )


@extend_schema(tags=["Teacher finance"])
class TeacherFinanceBalanceView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsTeacher,
    ]

    def get(self, request):
        currency = _teacher_finance_currency(
            request,
            default=TEACHER_FINANCE_CURRENCY,
        )

        balance = PaymentService.balance(
            teacher=request.user.teacher_profile,
            currency=currency,
        )

        serializer = TeacherBalanceSerializer(balance)

        return Response(serializer.data)


@extend_schema(tags=["Staff finance"])
class StaffTeacherBalanceView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsFinanceOperator,
    ]

    def get(
        self,
        request,
        teacher_id: int,
    ):
        teacher = get_object_or_404(
            TeacherProfile.objects.select_related("user"),
            pk=teacher_id,
        )

        currency = (
            str(
                request.query_params.get(
                    "currency",
                    TEACHER_FINANCE_CURRENCY,
                )
                or TEACHER_FINANCE_CURRENCY
            )
            .strip()
            .upper()
        )

        if currency != TEACHER_FINANCE_CURRENCY:
            raise ValidationError({"currency": ("Unsupported currency.")})

        result = PaymentService.balance(
            teacher=teacher,
            currency=currency,
        )

        balance_data = TeacherBalanceSerializer(result).data
        destinations = TeacherPayoutDestination.objects.filter(
            teacher=teacher,
            provider="liqpay",
            is_active=True,
        ).order_by("-is_default", "-created_at")
        balance_data["teacher"] = {
            "id": teacher.pk,
            "name": teacher.user.get_full_name() or teacher.user.email,
            "email": teacher.user.email,
        }
        balance_data["destinations"] = TeacherPayoutDestinationSerializer(
            destinations,
            many=True,
        ).data

        return Response(balance_data)


@extend_schema(tags=["Staff finance"])
class StaffTeacherPayoutViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [
        IsAuthenticated,
        IsFinanceOperator,
    ]

    http_method_names = [
        "get",
        "post",
        "head",
        "options",
    ]

    def get_queryset(self):
        queryset = TeacherPayout.objects.select_related(
            "teacher",
            "teacher__user",
            "destination",
            "created_by",
        ).order_by(
            "-created_at",
            "-id",
        )

        teacher_id = self.request.query_params.get("teacher")

        currency = (
            str(
                self.request.query_params.get(
                    "currency",
                    TEACHER_FINANCE_CURRENCY,
                )
                or TEACHER_FINANCE_CURRENCY
            )
            .strip()
            .upper()
        )

        payout_status = (
            str(
                self.request.query_params.get(
                    "status",
                    "",
                )
                or ""
            )
            .strip()
            .lower()
        )

        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        if currency:
            if currency != TEACHER_FINANCE_CURRENCY:
                raise ValidationError({"currency": ("Unsupported currency.")})

            queryset = queryset.filter(currency=currency)

        if payout_status:
            valid_statuses = {value for value, _ in TeacherPayout.StatusChoices.choices}

            if payout_status not in valid_statuses:
                raise ValidationError({"status": ("Unsupported payout status.")})

            queryset = queryset.filter(status=payout_status)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return StaffPayoutCreateSerializer

        return StaffTeacherPayoutSerializer

    def create(
        self,
        request,
        *args,
        **kwargs,
    ):
        serializer = StaffPayoutCreateSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        teacher = get_object_or_404(
            TeacherProfile.objects.select_related("user"),
            pk=data["teacher_id"],
        )

        destination_id = data.get("destination_id")

        if destination_id:
            destination = get_object_or_404(
                TeacherPayoutDestination.objects,
                pk=destination_id,
                teacher=teacher,
            )
        else:
            destination = TeacherPayoutDestination.objects.filter(
                teacher=teacher,
                provider="liqpay",
                is_active=True,
                is_default=True,
            ).first()

            if destination is None:
                raise ValidationError(
                    {"destination_id": ("Teacher has no active default payout destination.")}
                )

        existed_before = TeacherPayout.objects.filter(
            idempotency_key=(data["idempotency_key"])
        ).exists()

        try:
            payout = PaymentService.reserve_payout(
                teacher=teacher,
                destination=destination,
                amount=data["amount"],
                currency=data["currency"],
                idempotency_key=(data["idempotency_key"]),
                created_by=request.user,
            )

        except PaymentError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        output = StaffTeacherPayoutSerializer(
            payout,
            context={
                "request": request,
            },
        )

        return Response(
            output.data,
            status=(status.HTTP_200_OK if existed_before else status.HTTP_201_CREATED),
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="execute",
    )
    def execute(
        self,
        request,
        pk=None,
    ):
        payout = self.get_object()

        client_ip = str(
            request.META.get(
                "REMOTE_ADDR",
                "",
            )
            or ""
        ).strip()

        try:
            payout = PaymentService.execute_teacher_payout(
                payout=payout,
                client_ip=client_ip,
            )

        except PaymentError as exc:
            payout.refresh_from_db()

            # Transport was ambiguous. Do NOT turn
            # this into a normal validation failure.
            if (
                payout.status == TeacherPayout.StatusChoices.PROCESSING
                and payout.provider_status == "request_uncertain"
            ):
                data = StaffTeacherPayoutSerializer(payout).data

                return Response(
                    {
                        "detail": str(exc),
                        "payout": data,
                    },
                    status=(status.HTTP_502_BAD_GATEWAY),
                )

            raise ValidationError({"detail": str(exc)}) from exc

        return Response(StaffTeacherPayoutSerializer(payout).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="reconcile",
    )
    def reconcile(
        self,
        request,
        pk=None,
    ):
        payout = self.get_object()

        try:
            payout = PaymentService.reconcile_teacher_payout(payout=payout)

        except PaymentError as exc:
            payout.refresh_from_db()

            return Response(
                {
                    "detail": str(exc),
                    "payout": (StaffTeacherPayoutSerializer(payout).data),
                },
                status=(status.HTTP_502_BAD_GATEWAY),
            )

        return Response(StaffTeacherPayoutSerializer(payout).data)


@extend_schema(tags=["Teacher finance"])
class TeacherFinanceLedgerView(ListAPIView):
    permission_classes = [
        IsAuthenticated,
        IsTeacher,
    ]

    serializer_class = TeacherLedgerEntrySerializer

    def get_queryset(self):
        currency = _teacher_finance_currency(
            self.request,
            default=TEACHER_FINANCE_CURRENCY,
        )

        queryset = TeacherLedgerEntry.objects.filter(
            teacher=(self.request.user.teacher_profile)
        ).select_related(
            "payment",
            "refund",
            "payout",
        )

        if currency:
            queryset = queryset.filter(currency=currency)

        return queryset.order_by(
            "-created_at",
            "-id",
        )


@extend_schema(tags=["Teacher finance"])
class TeacherFinancePayoutHistoryView(ListAPIView):
    permission_classes = [
        IsAuthenticated,
        IsTeacher,
    ]

    serializer_class = TeacherPayoutSerializer

    def get_queryset(self):
        currency = _teacher_finance_currency(
            self.request,
            default=TEACHER_FINANCE_CURRENCY,
        )

        queryset = TeacherPayout.objects.filter(
            teacher=(self.request.user.teacher_profile)
        ).select_related(
            "destination",
        )

        if currency:
            queryset = queryset.filter(currency=currency)

        return queryset.order_by(
            "-created_at",
            "-id",
        )


@extend_schema(tags=["Teacher payouts"])
class TeacherPayoutStatusView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        payout = TeacherPayoutAccount.objects.filter(teacher=request.user.teacher_profile).first()
        return Response(PaymentService.safe_data(payout))


@extend_schema(tags=["Teacher payouts"])
class TeacherStripeFinanceView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsTeacher,
    ]

    def get(self, request):
        payout = TeacherPayoutAccount.objects.filter(teacher=request.user.teacher_profile).first()

        if payout is None:
            return Response(
                {
                    "configured": False,
                    "available": [],
                    "pending": [],
                    "payouts": [],
                }
            )

        try:
            result = PaymentService.stripe_finance_overview(
                payout,
                limit=10,
            )
        except PaymentError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(result)


@extend_schema(tags=["Teacher payouts"])
class TeacherPayoutOnboardingView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request):
        try:
            payout, url = PaymentService.create_onboarding_link(request.user.teacher_profile)
            return Response({**PaymentService.safe_data(payout), "onboarding_url": url})
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            logger.exception("Could not start Stripe Connect onboarding.")
            return Response(
                {"detail": "Could not start payout setup."}, status=status.HTTP_502_BAD_GATEWAY
            )


@extend_schema(tags=["Teacher payouts"])
class TeacherPayoutRefreshView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request):
        payout = TeacherPayoutAccount.objects.filter(teacher=request.user.teacher_profile).first()
        if payout is None:
            return Response(PaymentService.safe_data(None))
        try:
            return Response(PaymentService.safe_data(PaymentService.sync_account(payout)))
        except ImproperlyConfigured as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception:
            logger.exception("Could not refresh Stripe Connect account.")
            return Response(
                {"detail": "Could not refresh payout status."}, status=status.HTTP_502_BAD_GATEWAY
            )


def _derive_order_status(order: Order) -> str:
    payments = list(order.payments.all())

    captured_total = sum(
        (
            payment.amount
            for payment in payments
            if payment.status
            in {
                Payment.StatusChoices.SUCCEEDED,
                Payment.StatusChoices.REFUNDED,
            }
        ),
        0,
    )

    refunded_total = sum(
        (
            refund.amount
            for payment in payments
            for refund in payment.refunds.all()
            if refund.status == Refund.StatusChoices.SUCCEEDED
        ),
        0,
    )

    if refunded_total > 0:
        if captured_total > 0 and refunded_total >= captured_total:
            return "refunded"

        return "partially_refunded"

    if order.status == Order.StatusChoices.PAID:
        return "paid"

    if order.payment_type == Order.PaymentTypeChoices.INSTALLMENTS:
        today = timezone.now().date()

        overdue = any(
            installment.status == PaymentInstallment.StatusChoices.PENDING
            and installment.due_date < today
            for installment in order.installments.all()
        )

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
        queryset = Payment.objects.select_related(
            "user",
            "student_profile__user",
            "order",
            "order__user",
            "installment",
        ).prefetch_related(
            "items",
            "items__course",
            "items__pricing_plan",
            "order__items",
            "order__items__course",
            "order__items__pricing_plan",
            "order__installments",
            "order__payments",
            "refunds",
        )
        user = self.request.user
        if user.role == User.RoleChoices.ADMINISTRATOR:
            return queryset
        return queryset.filter(user=user)

    def get_permissions(self):
        if self.action in {
            "create_checkout_session",
            "create_payment_intent",
            "create_liqpay_checkout",
            "sync_payment_intent_status",
            "sync_liqpay_status",
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
        rows = PaymentService.revenue_by_category(self.filter_queryset(self.get_queryset()))
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
        summary="Refund a payment (administrators only)",
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
                {"detail": "Could not refund the payment."},
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
        request=LiqPayCheckoutCreateSerializer,
        responses={201: LiqPayCheckoutSerializer},
        summary="Create a LiqPay checkout for the current student's cart",
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="liqpay/checkout",
        url_name="liqpay-checkout",
    )
    def create_liqpay_checkout(self, request, *args, **kwargs):
        serializer = LiqPayCheckoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment, attempt, checkout = PaymentService.create_liqpay_checkout(
                user=request.user,
                selected_cart_item_ids=serializer.validated_data.get("selected_cart_item_ids"),
                payment_type=serializer.validated_data.get(
                    "payment_type",
                    Order.PaymentTypeChoices.FULL,
                ),
                installments_count=serializer.validated_data.get("installments_count"),
            )
        except PermissionDenied as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )
        except PaymentError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ImproperlyConfigured as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.exception("Could not create LiqPay checkout.")
            return Response(
                {"detail": "Could not create LiqPay checkout."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "checkout_url": checkout["checkout_url"],
                "data": checkout["data"],
                "signature": checkout["signature"],
                "provider_order_id": attempt.provider_order_id,
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "installment_id": payment.installment_id,
                "amount": f"{payment.amount:.2f}",
                "currency": payment.currency,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=LiqPayStatusSyncSerializer,
        responses={200: LiqPayStatusSerializer},
        summary="Sync LiqPay payment status",
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="liqpay/status/sync",
        url_name="liqpay-status-sync",
    )
    def sync_liqpay_status(
        self,
        request,
        *args,
        **kwargs,
    ):
        serializer = LiqPayStatusSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = (
            self.get_queryset()
            .filter(
                pk=serializer.validated_data["payment_id"],
                payment_method=Payment.MethodChoices.LIQPAY,
            )
            .first()
        )

        if payment is None:
            return Response(
                {"detail": "LiqPay payment was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payment, provider_status = PaymentService.sync_liqpay_payment_status(
                payment=payment,
            )

        except PaymentError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except ImproperlyConfigured as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except Exception:
            logger.exception("Could not sync LiqPay payment status.")
            return Response(
                {"detail": ("Could not sync LiqPay payment status.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        payment.refresh_from_db()

        return Response(
            {
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "installment_id": payment.installment_id,
                "payment_status": payment.status,
                "provider_status": provider_status,
            },
            status=status.HTTP_200_OK,
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
        queryset = Order.objects.select_related("user", "student_profile__user").prefetch_related(
            "items",
            "items__course",
            "items__pricing_plan",
            "installments",
            "payments",
        )
        user = self.request.user
        if user.role == User.RoleChoices.ADMINISTRATOR:
            return queryset
        return queryset.filter(user=user)

    def get_permissions(self):
        if self.action in {
            "create_installment_checkout_session",
            "create_installment_payment_intent",
            "create_installment_liqpay_checkout",
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

    @extend_schema(
        request=None,
        responses={201: LiqPayCheckoutSerializer},
        summary="Create a LiqPay checkout for an order installment",
    )
    @action(
        detail=True,
        methods=["post"],
        url_path=r"installments/(?P<installment_id>\d+)/liqpay/checkout",
        url_name="installment-liqpay-checkout",
    )
    def create_installment_liqpay_checkout(
        self,
        request,
        installment_id=None,
        *args,
        **kwargs,
    ):
        order = self.get_object()

        try:
            payment, attempt, checkout = PaymentService.create_installment_liqpay_checkout(
                user=request.user,
                order_id=order.id,
                installment_id=int(installment_id),
            )
        except PermissionDenied as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )
        except PaymentError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ImproperlyConfigured as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.exception("Could not create LiqPay installment checkout.")
            return Response(
                {"detail": ("Could not create LiqPay installment checkout.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "checkout_url": checkout["checkout_url"],
                "data": checkout["data"],
                "signature": checkout["signature"],
                "provider_order_id": attempt.provider_order_id,
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
    """GET /orders/teacher/: one row per (student, course) purchase across
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
            .prefetch_related("items__course", "items__cohort", "installments", "payments__refunds")
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
                (
                    i.due_date
                    for i in order.installments.all()
                    if i.status == PaymentInstallment.StatusChoices.PENDING
                ),
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
                rows.append(
                    {
                        "order_id": order.id,
                        "student_id": order.student_profile_id,
                        "student_name": order.student_profile.user.get_full_name(),
                        "student_avatar": absolute_media_url(
                            order.student_profile.user.avatar, request
                        ),
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
                    }
                )

        courses = Course.objects.filter(teacher_profile=teacher_profile)
        cohorts_qs = (
            Cohort.objects.filter(course__teacher_profile=teacher_profile, course__slug=course_slug)
            if course_slug
            else Cohort.objects.none()
        )

        return Response(
            {
                "results": rows,
                "courses": [{"slug": c.slug, "title": c.title} for c in courses],
                "cohorts": [{"id": c.id, "name": c.name or f"Group {c.id}"} for c in cohorts_qs],
            }
        )


@extend_schema(tags=["Orders"])
class TeacherOrderInvoiceView(APIView):
    """GET /orders/teacher/<order_id>/invoice/: download the invoice PDF for
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


@extend_schema(tags=["Teacher finance"])
class LiqPayPayoutCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def post(
        self,
        request,
        *args,
        **kwargs,
    ):
        data = request.data.get(
            "data",
            "",
        )

        signature = request.data.get(
            "signature",
            "",
        )

        if not data or not signature:
            return Response(
                {"detail": ("LiqPay payout callback data and signature are required.")},
                status=(status.HTTP_400_BAD_REQUEST),
            )

        try:
            payout = PaymentService.handle_liqpay_payout_callback(
                data=data,
                signature=signature,
            )

        except ImproperlyConfigured as exc:
            return Response(
                {"detail": str(exc)},
                status=(status.HTTP_503_SERVICE_UNAVAILABLE),
            )

        except PaymentError as exc:
            return Response(
                {"detail": str(exc)},
                status=(status.HTTP_400_BAD_REQUEST),
            )

        except Exception:
            logger.exception("Could not process LiqPay teacher payout callback.")

            return Response(
                {"detail": ("Could not process LiqPay payout callback.")},
                status=(status.HTTP_500_INTERNAL_SERVER_ERROR),
            )

        return Response(
            {
                "received": True,
                "payout_id": payout.id,
                "status": payout.status,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Payments"])
class LiqPayCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def post(self, request, *args, **kwargs):
        data = request.data.get("data", "")
        signature = request.data.get("signature", "")

        if not data or not signature:
            return Response(
                {"detail": "LiqPay callback data and signature are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            PaymentService.handle_liqpay_callback(
                data=data,
                signature=signature,
            )
        except ImproperlyConfigured as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except PaymentError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("Could not process LiqPay callback.")
            return Response(
                {"detail": "Could not process LiqPay callback."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"received": True},
            status=status.HTTP_200_OK,
        )
