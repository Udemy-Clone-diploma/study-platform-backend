from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode
from io import BytesIO
import json
import stripe
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import override_settings

from apps.users.models import User
from apps.cart.models import Cart, CartItem
from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_pricing_plan, make_teacher
from apps.enrollments.models import Enrollment
from apps.enrollments.services import EnrollmentService
from apps.enrollments.tests._factories import make_student
from apps.notifications.models import Notification
from apps.payments.models import (
    Order,
    OrderItem,
    Payment,
    PaymentAttempt,
    PaymentInstallment,
    PaymentItem,
    TeacherPayoutAccount,
    WebhookEvent,
    Refund,
    TeacherLedgerEntry,
    TeacherPayout,
    TeacherPayoutDestination,
    TeacherPayoutItem,
)
from apps.payments.services import (
    PaymentError,
    PaymentService,
    RefundError,
)
from apps.payments.services.liqpay import LiqPayService
from apps.payments.services.teacher_finance import (
    TeacherFinanceService,
)

class TeacherFinanceTests(APITestCase):
    def setUp(self):
        self.teacher_user, self.teacher_profile = make_teacher(
            email="teacher-finance@example.com"
        )

        self.payout_destination = (
            TeacherPayoutDestination.objects.create(
                teacher=self.teacher_profile,
                provider="liqpay",
                destination_type=(
                    TeacherPayoutDestination
                    .TypeChoices
                    .BANK_ACCOUNT
                ),
                receiver_account=(
                    "UA123456789012345678901234567"
                ),
                receiver_mfo="305299",
                receiver_okpo="1234567890",
                receiver_company="Test Teacher",
                is_default=True,
                is_active=True,
            )
        )

        self.admin_user = User.objects.create_user(
            email="finance-admin@example.com",
            password="pass12345",
            role=User.RoleChoices.ADMINISTRATOR,
        )

        self.moderator_user = (
            User.objects.create_user(
                email="finance-moderator@example.com",
                password="pass12345",
                role=User.RoleChoices.MODERATOR,
            )
        )
        self.student_user, self.student_profile = make_student(
            email="teacher-finance-student@example.com"
        )

        self.course = make_course(
            self.teacher_profile,
            title="Teacher Finance Course",
            slug="teacher-finance-course",
            status=Course.StatusChoices.PUBLISHED,
        )

        self.plan = make_pricing_plan(
            self.course,
            price="100.00",
        )

        self.cart = Cart.objects.create(
            student_profile=self.student_profile
        )

        CartItem.objects.create(
            cart=self.cart,
            course=self.course,
            pricing_plan=self.plan,
        )

    def test_liqpay_payment_success_creates_teacher_earning_once(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=(
                Payment.MethodChoices.LIQPAY
            ),
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.status,
            Payment.StatusChoices.SUCCEEDED,
        )

        entry = TeacherLedgerEntry.objects.get(
            source_key=(
                f"payment:{payment.id}:earning"
            )
        )

        self.assertEqual(
            entry.teacher,
            self.teacher_profile,
        )

        self.assertEqual(
            entry.entry_type,
            TeacherLedgerEntry.TypeChoices.EARNING,
        )

        self.assertEqual(
            entry.status,
            TeacherLedgerEntry.StatusChoices.POSTED,
        )

        self.assertEqual(
            entry.amount,
            Decimal("80.00"),
        )

        self.assertEqual(
            entry.currency,
            "UAH",
        )

        self.assertEqual(
            entry.payment,
            payment,
        )

        # Same provider callback/status sync again.
        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        self.assertEqual(
            TeacherLedgerEntry.objects.filter(
                source_key=(
                    f"payment:{payment.id}:earning"
                )
            ).count(),
            1,
        )

    def test_admin_can_reserve_teacher_payout_api(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="USD",
            payment_method=(
                Payment.MethodChoices.LIQPAY
            ),
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        self.client.force_authenticate(
            user=self.admin_user
        )

        response = self.client.post(
            reverse(
                "staff-finance-payouts-list"
            ),
            {
                "teacher_id": (
                    self.teacher_profile.id
                ),
                "destination_id": (
                    self.payout_destination.id
                ),
                "amount": "50.00",
                "currency": "USD",
                "idempotency_key": (
                    "admin-api-payout-1"
                ),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        payout = TeacherPayout.objects.get(
            idempotency_key=(
                "admin-api-payout-1"
            )
        )

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.PENDING,
        )

        self.assertEqual(
            payout.created_by,
            self.admin_user,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="USD",
        )

        self.assertEqual(
            balance["reserved"],
            Decimal("50.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("30.00"),
        )

    def test_staff_finance_rejects_unsupported_currency(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            reverse(
                "staff-teacher-finance-balance",
                kwargs={"teacher_id": self.teacher_profile.pk},
            ),
            {"currency": "UAH"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("currency", response.data)

    def test_staff_balance_uses_teacher_profile_and_masks_destinations(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            reverse(
                "staff-teacher-finance-balance",
                kwargs={"teacher_id": self.teacher_profile.pk},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["teacher"]["id"], self.teacher_profile.pk)
        self.assertEqual(len(response.data["destinations"]), 1)
        self.assertNotIn("receiver_card_token", response.data["destinations"][0])

    @override_settings(
        LIQPAY_PAYOUT_MODE="simulated",
        LIQPAY_SIMULATED_PAYOUT_OUTCOME="success",
    )
    def test_moderator_can_execute_teacher_payout_api(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=(
                Payment.MethodChoices.LIQPAY
            ),
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key=(
                "moderator-execute-payout"
            ),
            created_by=self.admin_user,
        )

        self.client.force_authenticate(
            user=self.moderator_user
        )

        response = self.client.post(
            reverse(
                "staff-finance-payouts-execute",
                args=[payout.id],
            ),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            payout.provider_status,
            "simulated_success",
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["paid"],
            Decimal("50.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("30.00"),
        )

    @override_settings(
        LIQPAY_PAYOUT_MODE="liqpay_sandbox",
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
        LIQPAY_API_VERSION=7,
        LIQPAY_API_URL=(
            "https://www.liqpay.ua/api/request"
        ),
    )
    @patch.object(
        LiqPayService,
        "_liqpay_send_request",
    )
    def test_execute_liqpay_payout_handles_b2c_failure(
        self,
        mock_send_request,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key="liqpay-b2c-failure-test",
        )

        mock_send_request.return_value = {
            "result": "error",
            "payment_id": 2912407823,
            "action": "p2pcredit",
            "status": "failure",
            "err_code": "err_b2c_settings",
            "err_description": (
                "B2C settings not defined"
            ),
            "version": 7,
            "type": "p2pcredit",
            "public_key": "sandbox_test_public",
            "order_id": (
                f"nexo-teacher-payout-{payout.id}"
            ),
            "transaction_id": 2912407823,
        }

        payout = (
            PaymentService.execute_teacher_payout(
                payout=payout,
                client_ip="203.0.113.10",
            )
        )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.FAILED,
        )

        self.assertEqual(
            payout.provider_status,
            "failure",
        )

        self.assertEqual(
            payout.provider_order_id,
            f"nexo-teacher-payout-{payout.id}",
        )

        self.assertEqual(
            payout.metadata["provider_response"][
                "err_code"
            ],
            "err_b2c_settings",
        )

        self.assertEqual(
            payout.metadata["provider_response"][
                "err_description"
            ],
            "B2C settings not defined",
        )

        self.assertFalse(
            payout.metadata["request_uncertain"]
        )

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.VOID,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["reserved"],
            Decimal("0.00"),
        )

        self.assertEqual(
            balance["paid"],
            Decimal("0.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("80.00"),
        )

        mock_send_request.assert_called_once()

    @override_settings(
        LIQPAY_PAYOUT_MODE="liqpay_sandbox",
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
        LIQPAY_API_VERSION=7,
        LIQPAY_API_URL=(
            "https://www.liqpay.ua/api/request"
        ),
    )
    @patch.object(
        LiqPayService,
        "_liqpay_send_request",
    )
    def test_execute_liqpay_payout_success(
        self,
        mock_send_request,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key="liqpay-success-test",
        )

        mock_send_request.return_value = {
            "result": "ok",
            "payment_id": 777001,
            "transaction_id": 888001,
            "action": "p2pcredit",
            "status": "success",
            "version": 7,
            "public_key": "sandbox_test_public",
            "order_id": (
                f"nexo-teacher-payout-{payout.id}"
            ),
        }

        payout = (
            PaymentService.execute_teacher_payout(
                payout=payout,
                client_ip="203.0.113.10",
            )
        )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            payout.provider_status,
            "success",
        )

        self.assertEqual(
            payout.provider_payment_id,
            "777001",
        )

        self.assertEqual(
            payout.provider_transaction_id,
            "888001",
        )

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.POSTED,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["paid"],
            Decimal("50.00"),
        )

        self.assertEqual(
            balance["reserved"],
            Decimal("0.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("30.00"),
        )

    @override_settings(
        LIQPAY_PAYOUT_MODE="liqpay_sandbox",
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
    )
    @patch.object(
        LiqPayService,
        "_liqpay_send_request",
    )
    def test_processing_payout_is_not_sent_twice(
        self,
        mock_send_request,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key=(
                "liqpay-no-double-send-test"
            ),
        )

        payout = (
            PaymentService
            ._prepare_payout_execution(
                payout,
                payout_mode="liqpay_sandbox",
            )[0]
        )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.PROCESSING,
        )

        result = (
            PaymentService.execute_teacher_payout(
                payout=payout,
                client_ip="203.0.113.10",
            )
        )

        self.assertEqual(
            result.status,
            TeacherPayout.StatusChoices.PROCESSING,
        )

        mock_send_request.assert_not_called()

    @override_settings(
        LIQPAY_PAYOUT_MODE="liqpay_sandbox",
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
    )
    def test_reconcile_uncertain_payout_to_failure(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key=(
                "reconcile-uncertain-failure"
            ),
        )

        with patch.object(
            LiqPayService,
            "_liqpay_send_request",
            side_effect=PaymentError(
                "Connection lost."
            ),
        ):
            with self.assertRaises(PaymentError):
                (
                    PaymentService
                    .execute_teacher_payout(
                        payout=payout,
                        client_ip="203.0.113.10",
                    )
                )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.PROCESSING,
        )

        self.assertTrue(
            payout.metadata["request_uncertain"]
        )

        with patch.object(
            LiqPayService,
            "_liqpay_get_payment_status",
            return_value={
                "result": "error",
                "action": "p2pcredit",
                "status": "failure",
                "err_code": "err_b2c_settings",
                "err_description": (
                    "B2C settings not defined"
                ),
                "version": 7,
                "public_key": (
                    "sandbox_test_public"
                ),
                "order_id": (
                    payout.provider_order_id
                ),
                "payment_id": 2912407823,
                "transaction_id": 2912407823,
            },
        ):
            payout = (
                PaymentService
                .reconcile_teacher_payout(
                    payout=payout
                )
            )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.FAILED,
        )

        self.assertFalse(
            payout.metadata["request_uncertain"]
        )

        self.assertEqual(
            payout.provider_payment_id,
            "2912407823",
        )

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.VOID,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["available"],
            Decimal("80.00"),
        )

    @override_settings(
        LIQPAY_PAYOUT_MODE="liqpay_sandbox",
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
    )
    @patch.object(
        LiqPayService,
        "_liqpay_get_payment_status",
    )
    def test_reconcile_processing_payout_to_success(
        self,
        mock_status,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key=(
                "reconcile-success-test"
            ),
        )

        payout, _ = (
            PaymentService
            ._prepare_payout_execution(
                payout,
                payout_mode="liqpay_sandbox",
            )
        )

        mock_status.return_value = {
            "result": "ok",
            "action": "p2pcredit",
            "status": "success",
            "version": 7,
            "public_key": "sandbox_test_public",
            "order_id": payout.provider_order_id,
            "payment_id": 777001,
            "transaction_id": 888001,
        }

        payout = (
            PaymentService
            .reconcile_teacher_payout(
                payout=payout
            )
        )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            payout.provider_payment_id,
            "777001",
        )

        self.assertEqual(
            payout.provider_transaction_id,
            "888001",
        )

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.POSTED,
        )

    @override_settings(
        LIQPAY_PAYOUT_MODE="liqpay_sandbox",
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
        LIQPAY_API_VERSION=7,
        LIQPAY_API_URL=(
            "https://www.liqpay.ua/api/request"
        ),
    )
    @patch.object(
        LiqPayService,
        "_liqpay_send_request",
    )
    def test_execute_liqpay_payout_network_error_is_uncertain(
        self,
        mock_send_request,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key=(
                "liqpay-network-uncertain-test"
            ),
        )

        mock_send_request.side_effect = PaymentError(
            "Could not connect to LiqPay API."
        )

        with self.assertRaises(PaymentError):
            PaymentService.execute_teacher_payout(
                payout=payout,
                client_ip="203.0.113.10",
            )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.PROCESSING,
        )

        self.assertEqual(
            payout.provider_status,
            "request_uncertain",
        )

        self.assertEqual(
            payout.provider_order_id,
            f"nexo-teacher-payout-{payout.id}",
        )

        self.assertTrue(
            payout.metadata["request_uncertain"]
        )

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.PENDING,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["reserved"],
            Decimal("50.00"),
        )

        self.assertEqual(
            balance["paid"],
            Decimal("0.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("30.00"),
        )

        mock_send_request.assert_called_once()

    def test_refund_adjustments_do_not_lose_rounding_cents(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.SUCCEEDED,
            processed_at=timezone.now(),
        )

        refunds = []

        for amount in [
            Decimal("33.33"),
            Decimal("33.33"),
            Decimal("33.34"),
        ]:
            refund = Refund.objects.create(
                payment=payment,
                amount=amount,
                provider=Payment.MethodChoices.LIQPAY,
                status=Refund.StatusChoices.PENDING,
            )

            entry = (
                TeacherFinanceService
                .ensure_refund_reservation(refund)
            )

            entry.post()
            refund.status = Refund.StatusChoices.SUCCEEDED
            refund.save(update_fields=["status"])

            refunds.append(entry)

        amounts = [
            entry.amount
            for entry in refunds
        ]

        self.assertEqual(
            amounts,
            [
                Decimal("-26.66"),
                Decimal("-26.67"),
                Decimal("-26.67"),
            ],
        )

        self.assertEqual(
            sum(amounts, Decimal("0.00")),
            Decimal("-80.00"),
        )

    @patch.object(
        LiqPayService,
        "_liqpay_create_refund",
    )
    def test_failed_liqpay_refund_voids_teacher_adjustment(
        self,
        mock_refund,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        PaymentAttempt.objects.create(
            payment=payment,
            provider=Payment.MethodChoices.LIQPAY,
            provider_order_id="teacher-refund-failed",
            provider_status="success",
            status=Payment.StatusChoices.SUCCEEDED,
            processed_at=timezone.now(),
        )

        mock_refund.return_value = {
            "result": "error",
            "status": "failure",
        }

        with self.assertRaises(PaymentError):
            PaymentService.refund_payment(
                payment=payment,
                amount=Decimal("25.00"),
            )

        refund = Refund.objects.get(
            payment=payment
        )

        adjustment = TeacherLedgerEntry.objects.get(
            refund=refund
        )

        self.assertEqual(
            refund.status,
            Refund.StatusChoices.FAILED,
        )

        self.assertEqual(
            adjustment.amount,
            Decimal("-20.00"),
        )

        self.assertEqual(
            adjustment.status,
            TeacherLedgerEntry.StatusChoices.VOID,
        )

    @override_settings(
        LIQPAY_PAYOUT_MODE="simulated",
        LIQPAY_SIMULATED_PAYOUT_OUTCOME="success",
    )
    def test_execute_simulated_payout_succeeds(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key=(
                "simulated-execution-success"
            ),
        )

        payout = (
            PaymentService.execute_teacher_payout(
                payout=payout,
            )
        )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            payout.provider_status,
            "simulated_success",
        )

        self.assertEqual(
            payout.provider_order_id,
            f"nexo-teacher-payout-{payout.id}",
        )

        self.assertEqual(
            payout.provider_payment_id,
            f"sim-payment-{payout.id}",
        )

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.POSTED,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["paid"],
            Decimal("50.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("30.00"),
        )

        self.assertEqual(
            payout.metadata["payout_mode"],
            "simulated",
        )

    @override_settings(
        LIQPAY_PAYOUT_MODE="simulated",
        LIQPAY_SIMULATED_PAYOUT_OUTCOME="failure",
    )
    def test_execute_simulated_payout_failure_releases_balance(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key=(
                "simulated-execution-failure"
            ),
        )

        payout = (
            PaymentService.execute_teacher_payout(
                payout=payout,
            )
        )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.FAILED,
        )

        self.assertEqual(
            payout.provider_status,
            "simulated_failure",
        )

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.VOID,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["reserved"],
            Decimal("0.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("80.00"),
        )

    @patch.object(
        LiqPayService,
        "_liqpay_create_refund",
    )
    def test_successful_liqpay_refund_posts_teacher_adjustment(
        self,
        mock_refund,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        PaymentAttempt.objects.create(
            payment=payment,
            provider=Payment.MethodChoices.LIQPAY,
            provider_order_id="teacher-refund-success",
            provider_status="success",
            status=Payment.StatusChoices.SUCCEEDED,
            processed_at=timezone.now(),
        )

        mock_refund.return_value = {
            "result": "ok",
            "wait_amount": False,
            "payment_id": 123456,
            "status": "reversed",
        }

        PaymentService.refund_payment(
            payment=payment,
            amount=Decimal("25.00"),
        )

        refund = Refund.objects.get(
            payment=payment
        )

        adjustment = TeacherLedgerEntry.objects.get(
            refund=refund
        )

        self.assertEqual(
            adjustment.amount,
            Decimal("-20.00"),
        )

        self.assertEqual(
            adjustment.status,
            TeacherLedgerEntry.StatusChoices.POSTED,
        )

        self.assertIsNotNone(
            adjustment.posted_at
        )

    @patch.object(
        LiqPayService,
        "_liqpay_create_refund",
    )
    def test_pending_liqpay_refund_reserves_teacher_share(
        self,
        mock_refund,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        PaymentAttempt.objects.create(
            payment=payment,
            provider=Payment.MethodChoices.LIQPAY,
            provider_order_id="teacher-refund-pending",
            provider_status="success",
            status=Payment.StatusChoices.SUCCEEDED,
            processed_at=timezone.now(),
        )

        mock_refund.return_value = {
            "result": "ok",
            "wait_amount": True,
            "payment_id": 123456,
            "status": "processing",
        }

        PaymentService.refund_payment(
            payment=payment,
            amount=Decimal("25.00"),
        )

        refund = Refund.objects.get(
            payment=payment
        )

        adjustment = TeacherLedgerEntry.objects.get(
            refund=refund,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.REFUND
            ),
        )

        self.assertEqual(
            adjustment.amount,
            Decimal("-20.00"),
        )

        self.assertEqual(
            adjustment.status,
            TeacherLedgerEntry.StatusChoices.PENDING,
        )

    def test_teacher_ledger_and_payout_models(self):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.SUCCEEDED,
            processed_at=timezone.now(),
        )

        earning = TeacherLedgerEntry.objects.create(
            teacher=self.teacher_profile,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.EARNING
            ),
            status=(
                TeacherLedgerEntry.StatusChoices.POSTED
            ),
            amount=Decimal("80.00"),
            currency="UAH",
            payment=payment,
            source_key=f"payment:{payment.id}:earning",
            posted_at=timezone.now(),
        )

        payout = TeacherPayout.objects.create(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            destination_snapshot={
                "destination_type": (
                    self.payout_destination.destination_type
                ),
                "receiver_account": (
                    self.payout_destination.receiver_account
                ),
                "receiver_mfo": (
                    self.payout_destination.receiver_mfo
                ),
                "receiver_okpo": (
                    self.payout_destination.receiver_okpo
                ),
                "receiver_company": (
                    self.payout_destination.receiver_company
                ),
            },
            amount=Decimal("50.00"),
            currency="UAH",
            provider=TeacherPayout.ProviderChoices.LIQPAY,
            idempotency_key="teacher-payout-test-1",
        )

        item = TeacherPayoutItem.objects.create(
            payout=payout,
            payment=payment,
            amount=Decimal("50.00"),
            currency="UAH",
        )

        reservation = TeacherLedgerEntry.objects.create(
            teacher=self.teacher_profile,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
            status=(
                TeacherLedgerEntry.StatusChoices.PENDING
            ),
            amount=Decimal("-50.00"),
            currency="UAH",
            payout=payout,
            source_key=f"payout:{payout.id}:settlement",
        )

        self.assertEqual(
            earning.amount,
            Decimal("80.00"),
        )

        self.assertEqual(
            item.amount,
            Decimal("50.00"),
        )

        self.assertEqual(
            reservation.amount,
            Decimal("-50.00"),
        )

        reservation.post()
        reservation.refresh_from_db()

        self.assertEqual(
            reservation.status,
            TeacherLedgerEntry.StatusChoices.POSTED,
        )

        self.assertIsNotNone(
            reservation.posted_at
        )

    def test_teacher_balance_is_currency_specific(
        self,
    ):
        TeacherLedgerEntry.objects.create(
            teacher=self.teacher_profile,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.EARNING
            ),
            status=(
                TeacherLedgerEntry.StatusChoices.POSTED
            ),
            amount=Decimal("100.00"),
            currency="UAH",
            source_key="currency-uah",
            posted_at=timezone.now(),
        )

        TeacherLedgerEntry.objects.create(
            teacher=self.teacher_profile,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.EARNING
            ),
            status=(
                TeacherLedgerEntry.StatusChoices.POSTED
            ),
            amount=Decimal("50.00"),
            currency="USD",
            source_key="currency-usd",
            posted_at=timezone.now(),
        )

        uah = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        usd = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="USD",
        )

        self.assertEqual(
            uah["available"],
            Decimal("100.00"),
        )

        self.assertEqual(
            usd["available"],
            Decimal("50.00"),
        )

    def test_teacher_balance_can_be_negative(
        self,
    ):
        TeacherLedgerEntry.objects.create(
            teacher=self.teacher_profile,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.EARNING
            ),
            status=(
                TeacherLedgerEntry.StatusChoices.POSTED
            ),
            amount=Decimal("80.00"),
            currency="UAH",
            source_key="negative-earning",
            posted_at=timezone.now(),
        )

        TeacherLedgerEntry.objects.create(
            teacher=self.teacher_profile,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
            status=(
                TeacherLedgerEntry.StatusChoices.POSTED
            ),
            amount=Decimal("-80.00"),
            currency="UAH",
            source_key="negative-payout",
            posted_at=timezone.now(),
        )

        TeacherLedgerEntry.objects.create(
            teacher=self.teacher_profile,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.REFUND
            ),
            status=(
                TeacherLedgerEntry.StatusChoices.POSTED
            ),
            amount=Decimal("-20.00"),
            currency="UAH",
            source_key="negative-refund",
            posted_at=timezone.now(),
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["earned"],
            Decimal("80.00"),
        )

        self.assertEqual(
            balance["paid"],
            Decimal("80.00"),
        )

        self.assertEqual(
            balance["refunded"],
            Decimal("20.00"),
        )

        self.assertEqual(
            balance["balance"],
            Decimal("-20.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("-20.00"),
        )
    def test_teacher_balance_includes_pending_refund_reservation(
        self,
    ):
        TeacherLedgerEntry.objects.create(
            teacher=self.teacher_profile,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.EARNING
            ),
            status=(
                TeacherLedgerEntry.StatusChoices.POSTED
            ),
            amount=Decimal("80.00"),
            currency="UAH",
            source_key="balance-earning-1",
            posted_at=timezone.now(),
        )

        TeacherLedgerEntry.objects.create(
            teacher=self.teacher_profile,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.REFUND
            ),
            status=(
                TeacherLedgerEntry.StatusChoices.PENDING
            ),
            amount=Decimal("-20.00"),
            currency="UAH",
            source_key="balance-refund-1",
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["earned"],
            Decimal("80.00"),
        )

        self.assertEqual(
            balance["refunded"],
            Decimal("0.00"),
        )

        self.assertEqual(
            balance["paid"],
            Decimal("0.00"),
        )

        self.assertEqual(
            balance["reserved"],
            Decimal("20.00"),
        )

        self.assertEqual(
            balance["balance"],
            Decimal("80.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("60.00"),
        )

    def test_teacher_payout_reservation_reduces_available_balance(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=(
                Payment.MethodChoices.LIQPAY
            ),
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        before = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            before["available"],
            Decimal("80.00"),
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key="teacher-payout-1",
        )

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.PENDING,
        )

        self.assertEqual(
            payout.amount,
            Decimal("50.00"),
        )

        item = TeacherPayoutItem.objects.get(
            payout=payout
        )

        self.assertEqual(
            item.payment,
            payment,
        )

        self.assertEqual(
            item.amount,
            Decimal("50.00"),
        )

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            ledger.amount,
            Decimal("-50.00"),
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.PENDING,
        )

        after = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            after["reserved"],
            Decimal("50.00"),
        )

        self.assertEqual(
            after["available"],
            Decimal("30.00"),
        )
    def test_teacher_cannot_reserve_payout_above_available_balance(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        with self.assertRaises(PaymentError):
            PaymentService.reserve_payout(
                teacher=self.teacher_profile,
                destination=self.payout_destination,
                amount=Decimal("80.01"),
                currency="UAH",
                idempotency_key="too-large-payout",
            )

        self.assertFalse(
            TeacherPayout.objects.filter(
                idempotency_key="too-large-payout"
            ).exists()
        )
    def test_teacher_payout_reservation_is_idempotent(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        first = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key="same-payout-request",
        )

        second = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key="same-payout-request",
        )

        self.assertEqual(
            first.id,
            second.id,
        )

        self.assertEqual(
            TeacherPayout.objects.filter(
                idempotency_key="same-payout-request"
            ).count(),
            1,
        )

        self.assertEqual(
            TeacherLedgerEntry.objects.filter(
                payout=first,
                entry_type=(
                    TeacherLedgerEntry.TypeChoices.PAYOUT
                ),
            ).count(),
            1,
        )

        self.assertEqual(
            TeacherPayoutItem.objects.filter(
                payout=first
            ).count(),
            1,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["available"],
            Decimal("30.00"),
        )

    def test_teacher_payout_can_allocate_multiple_payments(
        self,
    ):
        payments = []

        for index in range(2):
            payment = Payment.objects.create(
                user=self.student_user,
                student_profile=self.student_profile,
                teacher=self.teacher_profile,
                amount=Decimal("100.00"),
                gross_amount=Decimal("100.00"),
                platform_fee_amount=Decimal("20.00"),
                teacher_amount=Decimal("80.00"),
                currency="UAH",
                payment_method=Payment.MethodChoices.LIQPAY,
                status=Payment.StatusChoices.PENDING,
            )

            PaymentService._complete_successful_payment(
                payment,
                record_attempt=False,
            )

            payments.append(payment)

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("100.00"),
            currency="UAH",
            idempotency_key="multi-payment-payout",
        )

        items = list(
            payout.items.order_by("id")
        )

        self.assertEqual(
            len(items),
            2,
        )

        self.assertEqual(
            sum(
                (
                    item.amount
                    for item in items
                ),
                Decimal("0.00"),
            ),
            Decimal("100.00"),
        )

        self.assertEqual(
            sorted(
                item.amount
                for item in items
            ),
            [
                Decimal("20.00"),
                Decimal("80.00"),
            ],
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["available"],
            Decimal("60.00"),
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
        LIQPAY_API_VERSION=7,
    )
    def test_liqpay_payout_callback_marks_failure(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=(
                Payment.MethodChoices.LIQPAY
            ),
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key=(
                "payout-callback-failure"
            ),
        )

        payout, _ = (
            PaymentService
            ._prepare_payout_execution(
                payout,
                payout_mode="liqpay_sandbox",
            )
        )

        payload = {
            "public_key": (
                "sandbox_test_public"
            ),
            "version": 7,
            "action": "p2pcredit",
            "order_id": (
                payout.provider_order_id
            ),
            "amount": "50.00",
            "currency": "UAH",
            "status": "failure",
            "result": "error",
            "err_code": "err_b2c_settings",
            "err_description": (
                "B2C settings not defined"
            ),
            "payment_id": 2912407823,
            "transaction_id": 2912407823,
        }

        data = (
            PaymentService
            ._liqpay_encode_payload(
                payload
            )
        )

        signature = (
            PaymentService
            ._liqpay_sign_data(
                data
            )
        )

        response = self.client.post(
            reverse(
                "liqpay-payout-callback"
            ),
            {
                "data": data,
                "signature": signature,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout
            .StatusChoices
            .FAILED,
        )

        ledger = (
            TeacherLedgerEntry.objects.get(
                payout=payout,
                entry_type=(
                    TeacherLedgerEntry
                    .TypeChoices
                    .PAYOUT
                ),
            )
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry
            .StatusChoices
            .VOID,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["reserved"],
            Decimal("0.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("80.00"),
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
        LIQPAY_API_VERSION=7,
    )
    def test_liqpay_payout_callback_rejects_bad_signature(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=(
                Payment.MethodChoices.LIQPAY
            ),
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key=(
                "payout-callback-bad-signature"
            ),
        )

        payout, _ = (
            PaymentService
            ._prepare_payout_execution(
                payout,
                payout_mode="liqpay_sandbox",
            )
        )

        payload = {
            "public_key": (
                "sandbox_test_public"
            ),
            "version": 7,
            "action": "p2pcredit",
            "order_id": (
                payout.provider_order_id
            ),
            "amount": "50.00",
            "currency": "UAH",
            "status": "success",
            "result": "ok",
        }

        data = (
            PaymentService
            ._liqpay_encode_payload(
                payload
            )
        )

        response = self.client.post(
            reverse(
                "liqpay-payout-callback"
            ),
            {
                "data": data,
                "signature": "invalid-signature",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout
            .StatusChoices
            .PROCESSING,
        )

        ledger = (
            TeacherLedgerEntry.objects.get(
                payout=payout,
                entry_type=(
                    TeacherLedgerEntry
                    .TypeChoices
                    .PAYOUT
                ),
            )
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry
            .StatusChoices
            .PENDING,
        )



    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
        LIQPAY_API_VERSION=7,
    )
    def test_liqpay_payout_callback_marks_success(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=(
                Payment.MethodChoices.LIQPAY
            ),
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key=(
                "payout-callback-success"
            ),
        )

        payout, should_send = (
            PaymentService
            ._prepare_payout_execution(
                payout,
                payout_mode="liqpay_sandbox",
            )
        )

        self.assertTrue(should_send)

        payload = {
            "public_key": (
                "sandbox_test_public"
            ),
            "version": 7,
            "action": "p2pcredit",
            "order_id": (
                payout.provider_order_id
            ),
            "amount": "50.00",
            "currency": "UAH",
            "status": "success",
            "result": "ok",
            "payment_id": 777001,
            "transaction_id": 888001,
        }

        data = (
            PaymentService
            ._liqpay_encode_payload(
                payload
            )
        )

        signature = (
            PaymentService
            ._liqpay_sign_data(
                data
            )
        )

        response = self.client.post(
            reverse(
                "liqpay-payout-callback"
            ),
            {
                "data": data,
                "signature": signature,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        payout.refresh_from_db()

        self.assertEqual(
            payout.status,
            TeacherPayout
            .StatusChoices
            .SUCCEEDED,
        )

        self.assertEqual(
            payout.provider_payment_id,
            "777001",
        )

        self.assertEqual(
            payout.provider_transaction_id,
            "888001",
        )

        ledger = (
            TeacherLedgerEntry.objects.get(
                payout=payout,
                entry_type=(
                    TeacherLedgerEntry
                    .TypeChoices
                    .PAYOUT
                ),
            )
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry
            .StatusChoices
            .POSTED,
        )
        second_response = self.client.post(
        reverse(
            "liqpay-payout-callback"
        ),
        {
            "data": data,
            "signature": signature,
        },
        format="json",
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
        TeacherLedgerEntry.objects.filter(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry
                .TypeChoices
                .PAYOUT
            ),
        ).count(),
        1,
        )

    def test_processing_payout_keeps_money_reserved(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key="processing-payout",
        )

        PaymentService.mark_payout_processing(
            payout,
            provider_status="processing",
        )

        payout.refresh_from_db()

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.PROCESSING,
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.PENDING,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["reserved"],
            Decimal("50.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("30.00"),
        )

    def test_successful_payout_posts_ledger_entry(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            destination=self.payout_destination,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key="successful-payout",
        )

        PaymentService.mark_payout_processing(
            payout,
            provider_status="processing",
        )

        PaymentService.mark_payout_succeeded(
            payout,
            provider_status="success",
            provider_payment_id="777001",
            provider_transaction_id="888001",
        )

        payout.refresh_from_db()

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            payout.provider_payment_id,
            "777001",
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.POSTED,
        )

        self.assertIsNotNone(
            ledger.posted_at
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["earned"],
            Decimal("80.00"),
        )

        self.assertEqual(
            balance["paid"],
            Decimal("50.00"),
        )

        self.assertEqual(
            balance["reserved"],
            Decimal("0.00"),
        )

        self.assertEqual(
            balance["balance"],
            Decimal("30.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("30.00"),
        )

    def test_failed_payout_releases_reserved_balance(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key="failed-payout",
            destination=self.payout_destination,
        )

        PaymentService.mark_payout_processing(
            payout,
            provider_status="processing",
        )

        PaymentService.mark_payout_failed(
            payout,
            provider_status="failure",
            reason="Provider rejected payout.",
        )

        payout.refresh_from_db()

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            payout.status,
            TeacherPayout.StatusChoices.FAILED,
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.VOID,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["paid"],
            Decimal("0.00"),
        )

        self.assertEqual(
            balance["reserved"],
            Decimal("0.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("80.00"),
        )

    def test_successful_payout_transition_is_idempotent(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        payout = PaymentService.reserve_payout(
            teacher=self.teacher_profile,
            amount=Decimal("50.00"),
            currency="UAH",
            idempotency_key="idempotent-success-payout",
            destination=self.payout_destination,
        )

        PaymentService.mark_payout_succeeded(
            payout,
            provider_status="success",
            provider_payment_id="777001",
        )

        PaymentService.mark_payout_succeeded(
            payout,
            provider_status="success",
            provider_payment_id="777001",
        )

        ledger = TeacherLedgerEntry.objects.get(
            payout=payout,
            entry_type=(
                TeacherLedgerEntry.TypeChoices.PAYOUT
            ),
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry.StatusChoices.POSTED,
        )

        self.assertEqual(
            TeacherLedgerEntry.objects.filter(
                payout=payout,
                entry_type=(
                    TeacherLedgerEntry.TypeChoices.PAYOUT
                ),
            ).count(),
            1,
        )

        balance = PaymentService.balance(
            teacher=self.teacher_profile,
            currency="UAH",
        )

        self.assertEqual(
            balance["paid"],
            Decimal("50.00"),
        )

        self.assertEqual(
            balance["available"],
            Decimal("30.00"),
        )

    def test_teacher_finance_balance_api(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="USD",
            payment_method=(
                Payment.MethodChoices.LIQPAY
            ),
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        self.client.force_authenticate(
            user=self.teacher_user
        )

        response = self.client.get(
            reverse("teacher-finance-balance")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            Decimal(response.data["earned"]),
            Decimal("80.00"),
        )

        self.assertEqual(
            Decimal(response.data["available"]),
            Decimal("80.00"),
        )

        self.assertEqual(
            response.data["currency"],
            "USD",
        )

    def test_teacher_finance_ledger_only_own_entries(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=(
                Payment.MethodChoices.LIQPAY
            ),
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        self.client.force_authenticate(
            user=self.teacher_user
        )

        response = self.client.get(
            reverse("teacher-finance-ledger")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        data = (
            response.data.get("results")
            if isinstance(response.data, dict)
            and "results" in response.data
            else response.data
        )

        self.assertEqual(len(data), 1)

        self.assertEqual(
            data[0]["entry_type"],
            TeacherLedgerEntry
            .TypeChoices
            .EARNING,
        )

        self.assertEqual(
            Decimal(data[0]["amount"]),
            Decimal("80.00"),
        )

    def test_student_cannot_access_teacher_finance(
        self,
    ):
        self.client.force_authenticate(
            user=self.student_user
        )

        response = self.client.get(
            reverse("teacher-finance-balance")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_teacher_can_create_bank_payout_destination(
        self,
    ):
        self.payout_destination.is_default = False
        self.payout_destination.is_active = False

        self.payout_destination.save(
            update_fields=[
                "is_default",
                "is_active",
                "updated_at",
            ]
        )
        self.client.force_authenticate(
            user=self.teacher_user
        )

        response = self.client.post(
            reverse(
                "teacher-finance-destinations-list"
            ),
            {
                "destination_type": "bank_account",
                "receiver_account": (
                    "UA123456789012345678901234567"
                ),
                "receiver_mfo": "305299",
                "receiver_okpo": "1234567890",
                "receiver_company": "Test Teacher",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        destination = (
            TeacherPayoutDestination.objects.get(
                pk=response.data["id"]
            )
        )

        self.assertEqual(
            destination.teacher,
            self.teacher_profile,
        )

        self.assertTrue(
            destination.is_active
        )

        self.assertTrue(
            destination.is_default
        )

        self.assertNotIn(
            "receiver_account",
            response.data,
        )

    def test_teacher_cannot_store_raw_card_pan(
        self,
    ):
        self.client.force_authenticate(
            user=self.teacher_user
        )

        response = self.client.post(
            reverse(
                "teacher-finance-destinations-list"
            ),
            {
                "destination_type": "card_token",
                "receiver_card_token": (
                    "4242424242424242"
                ),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertFalse(
            TeacherPayoutDestination.objects
            .filter(
                teacher=self.teacher_profile,
                receiver_card_token=(
                    "4242424242424242"
                ),
            )
            .exists()
        )

    def test_teacher_can_store_liqpay_card_token(
        self,
    ):
        self.client.force_authenticate(
            user=self.teacher_user
        )

        response = self.client.post(
            reverse(
                "teacher-finance-destinations-list"
            ),
            {
                "destination_type": "card_token",
                "receiver_card_token": (
                    "sandbox_receiver_token_001"
                ),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            response.data["has_card_token"]
        )

        self.assertNotIn(
            "receiver_card_token",
            response.data,
        )

    def test_new_default_destination_clears_previous_default(
        self,
    ):
        first = (
            TeacherPayoutDestination.objects.create(
                teacher=self.teacher_profile,
                provider="liqpay",
                destination_type="card_token",
                receiver_card_token="token-first",
                is_active=True,
                is_default=True,
            )
        )

        self.client.force_authenticate(
            user=self.teacher_user
        )

        response = self.client.post(
            reverse(
                "teacher-finance-destinations-list"
            ),
            {
                "destination_type": "card_token",
                "receiver_card_token": (
                    "token-second"
                ),
                "is_default": True,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        first.refresh_from_db()

        second = (
            TeacherPayoutDestination.objects.get(
                pk=response.data["id"]
            )
        )

        self.assertFalse(
            first.is_default
        )

        self.assertTrue(
            second.is_default
        )

    def test_delete_destination_soft_deactivates_it(
        self,
    ):
        destination = (
            TeacherPayoutDestination.objects.create(
                teacher=self.teacher_profile,
                provider="liqpay",
                destination_type="card_token",
                receiver_card_token="token-delete",
                is_active=True,
                is_default=True,
            )
        )

        self.client.force_authenticate(
            user=self.teacher_user
        )

        response = self.client.delete(
            reverse(
                "teacher-finance-destinations-detail",
                args=[destination.id],
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        destination.refresh_from_db()

        self.assertFalse(
            destination.is_active
        )

        self.assertFalse(
            destination.is_default
        )

        self.assertTrue(
            TeacherPayoutDestination.objects
            .filter(pk=destination.pk)
            .exists()
        )

    def test_teacher_cannot_use_staff_payout_api(
        self,
    ):
        self.client.force_authenticate(
            user=self.teacher_user
        )

        response = self.client.get(
            reverse(
                "staff-finance-payouts-list"
            )
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_payout_create_api_is_idempotent(
        self,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="USD",
            payment_method=(
                Payment.MethodChoices.LIQPAY
            ),
            status=Payment.StatusChoices.PENDING,
        )

        PaymentService._complete_successful_payment(
            payment,
            record_attempt=False,
        )

        self.client.force_authenticate(
            user=self.admin_user
        )

        payload = {
            "teacher_id": self.teacher_profile.id,
            "destination_id": (
                self.payout_destination.id
            ),
            "amount": "50.00",
            "currency": "USD",
            "idempotency_key": (
                "staff-api-idempotent"
            ),
        }

        first = self.client.post(
            reverse(
                "staff-finance-payouts-list"
            ),
            payload,
            format="json",
        )

        second = self.client.post(
            reverse(
                "staff-finance-payouts-list"
            ),
            payload,
            format="json",
        )

        self.assertEqual(
            first.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            second.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            first.data["id"],
            second.data["id"],
        )

        self.assertEqual(
            TeacherPayout.objects.filter(
                idempotency_key=(
                    "staff-api-idempotent"
                )
            ).count(),
            1,
        )

@override_settings(
    LIQPAY_PUBLIC_KEY="i00000000",
    LIQPAY_PRIVATE_KEY="a4825234f4bae72a0be04eafe9e8e2bada209255",
    LIQPAY_API_VERSION=7,
)
class LiqPayServiceTests(APITestCase):
    def test_v7_signature_matches_official_liqpay_example(self):
        payload = {
            "public_key": "i00000000",
            "version": 7,
            "action": "pay",
            "amount": "3",
            "currency": "UAH",
            "description": "test",
            "order_id": "000001",
        }

        data = PaymentService._liqpay_encode_payload(payload)

        self.assertEqual(
            data,
            (
                "eyJwdWJsaWNfa2V5IjoiaTAwMDAwMDAwIiwidmVyc2lvbiI6Nywi"
                "YWN0aW9uIjoicGF5IiwiYW1vdW50IjoiMyIsImN1cnJlbmN5Ijoi"
                "VUFIIiwiZGVzY3JpcHRpb24iOiJ0ZXN0Iiwib3JkZXJfaWQiOiIw"
                "MDAwMDEifQ=="
            ),
        )

        signature = PaymentService._liqpay_sign_data(data)

        self.assertEqual(
            signature,
            "0adgJ8F2Ds5HCVkcz4AlmdLMRoIJf7IxsL3QmeFRz/s=",
        )

        self.assertTrue(
            PaymentService._liqpay_verify_signature(
                data=data,
                signature=signature,
            )
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
        LIQPAY_API_VERSION=7,
        LIQPAY_API_URL=(
            "https://www.liqpay.ua/api/request"
        ),
        LIQPAY_PAYOUT_SERVER_URL=(
            "https://api.example.com/api/v1/"
            "payments/liqpay/payout/callback/"
        ),
    )
    def test_build_liqpay_teacher_payout_request(
        self,
    ):
        teacher_user, teacher = make_teacher(
            email="liqpay-payout-builder@example.com"
        )

        destination = (
            TeacherPayoutDestination.objects.create(
                teacher=teacher,
                provider="liqpay",
                destination_type=(
                    TeacherPayoutDestination
                    .TypeChoices
                    .BANK_ACCOUNT
                ),
                receiver_account=(
                    "UA123456789012345678901234567"
                ),
                receiver_mfo="305299",
                receiver_okpo="1234567890",
                receiver_company="Test Teacher",
                is_active=True,
            )
        )

        payout = TeacherPayout.objects.create(
            teacher=teacher,
            destination=destination,
            destination_snapshot={
                "destination_type": (
                    "bank_account"
                ),
                "receiver_account": (
                    "UA123456789012345678901234567"
                ),
                "receiver_mfo": "305299",
                "receiver_okpo": "1234567890",
                "receiver_company": "Test Teacher",
            },
            amount=Decimal("50.00"),
            currency="UAH",
            provider=(
                TeacherPayout
                .ProviderChoices
                .LIQPAY
            ),
            idempotency_key=(
                "liqpay-builder-test-1"
            ),
        )

        request_data = (
            PaymentService
            ._liqpay_build_payout_request(
                payout=payout,
                client_ip="203.0.113.10",
                server_url=(
                    "https://api.example.com/api/v1/"
                    "payments/liqpay/payout/callback/"
                ),
            )
        )

        self.assertEqual(
            request_data["api_url"],
            "https://www.liqpay.ua/api/request",
        )

        self.assertTrue(
            request_data["data"]
        )

        self.assertTrue(
            request_data["signature"]
        )

        payload = (
            PaymentService
            ._liqpay_decode_data(
                request_data["data"]
            )
        )

        self.assertEqual(
            payload["public_key"],
            "sandbox_test_public",
        )

        self.assertEqual(
            payload["version"],
            7,
        )

        self.assertEqual(
            payload["action"],
            "p2pcredit",
        )

        self.assertEqual(
            payload["amount"],
            "50.00",
        )

        self.assertEqual(
            payload["currency"],
            "UAH",
        )

        self.assertEqual(
            payload["ip"],
            "203.0.113.10",
        )

        self.assertEqual(
            payload["server_url"],
            (
                "https://api.example.com/api/v1/"
                "payments/liqpay/payout/callback/"
            ),
        )

        self.assertEqual(
            payload["order_id"],
            f"nexo-teacher-payout-{payout.id}",
        )

        self.assertEqual(
            payload["receiver_account"],
            "UA123456789012345678901234567",
        )

        self.assertEqual(
            payload["receiver_mfo"],
            "305299",
        )

        self.assertEqual(
            payload["receiver_okpo"],
            "1234567890",
        )

        self.assertEqual(
            payload["receiver_company"],
            "Test Teacher",
        )

        self.assertTrue(
            PaymentService
            ._liqpay_verify_signature(
                data=request_data["data"],
                signature=(
                    request_data["signature"]
                ),
            )
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="production_public",
        LIQPAY_PRIVATE_KEY="production_private",
    )
    def test_liqpay_payout_rejects_non_sandbox_keys(
        self,
    ):
        with self.assertRaises(PaymentError):
            PaymentService._ensure_liqpay_payout_sandbox()

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
    )
    def test_liqpay_payout_accepts_sandbox_keys(
        self,
    ):
        PaymentService._ensure_liqpay_payout_sandbox()

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
        LIQPAY_API_URL="https://www.liqpay.ua/api/request",
    )
    def test_build_liqpay_status_request(self):
        request_data = (
            PaymentService._liqpay_build_status_request(
                provider_order_id=(
                    "nexo-payment-1-attempt-2"
                ),
            )
        )

        payload = PaymentService._liqpay_decode_data(
            request_data["data"]
        )

        self.assertEqual(
            payload,
            {
                "public_key": "sandbox_test_public",
                "version": 7,
                "action": "status",
                "order_id": (
                    "nexo-payment-1-attempt-2"
                ),
            },
        )

        self.assertTrue(
            PaymentService._liqpay_verify_signature(
                data=request_data["data"],
                signature=request_data["signature"],
            )
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
        LIQPAY_API_URL="https://www.liqpay.ua/api/request",
    )
    def test_build_liqpay_refund_request(self):
        refund_request = (
            PaymentService._liqpay_build_refund_request(
                provider_order_id="nexo-payment-25-attempt-40",
                amount=Decimal("25.00"),
            )
        )

        self.assertEqual(
            refund_request["api_url"],
            "https://www.liqpay.ua/api/request",
        )

        self.assertTrue(
            refund_request["data"]
        )

        self.assertTrue(
            refund_request["signature"]
        )

        payload = PaymentService._liqpay_decode_data(
            refund_request["data"]
        )

        self.assertEqual(
            payload,
            {
                "public_key": "sandbox_test_public",
                "version": 7,
                "action": "refund",
                "amount": "25.00",
                "order_id": "nexo-payment-25-attempt-40",
            },
        )

        self.assertTrue(
            PaymentService._liqpay_verify_signature(
                data=refund_request["data"],
                signature=refund_request["signature"],
            )
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
    )
    def test_build_partial_liqpay_refund_request(self):
        refund_request = (
            PaymentService._liqpay_build_refund_request(
                provider_order_id="nexo-payment-10-attempt-15",
                amount=Decimal("7.50"),
            )
        )

        payload = PaymentService._liqpay_decode_data(
            refund_request["data"]
        )

        self.assertEqual(
            payload["action"],
            "refund",
        )

        self.assertEqual(
            payload["amount"],
            "7.50",
        )

        self.assertEqual(
            payload["order_id"],
            "nexo-payment-10-attempt-15",
        )

    def test_liqpay_refund_rejects_non_positive_amount(self):
        with self.assertRaises(PaymentError):
            PaymentService._liqpay_build_refund_request(
                provider_order_id="test-order",
                amount=Decimal("0.00"),
            )
    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
        LIQPAY_API_URL="https://www.liqpay.ua/api/request",
        LIQPAY_HTTP_TIMEOUT=10,
    )
    @patch("apps.payments.services.liqpay.urlopen")
    def test_liqpay_create_refund_sends_server_server_request(
        self,
        mock_urlopen,
    ):
        response_body = json.dumps(
            {
                "result": "ok",
                "wait_amount": True,
                "payment_id": 2417662437,
                "status": "reversed",
            }
        ).encode("utf-8")

        mocked_response = BytesIO(response_body)

        mock_urlopen.return_value.__enter__.return_value = (
            mocked_response
        )

        response = PaymentService._liqpay_create_refund(
            provider_order_id="nexo-payment-1-attempt-1",
            amount=Decimal("10.00"),
        )

        self.assertEqual(
            response["result"],
            "ok",
        )

        self.assertEqual(
            response["status"],
            "reversed",
        )

        self.assertEqual(
            response["payment_id"],
            2417662437,
        )

        mock_urlopen.assert_called_once()

        request = mock_urlopen.call_args.args[0]

        self.assertEqual(
            request.full_url,
            "https://www.liqpay.ua/api/request",
        )

        self.assertEqual(
            request.get_method(),
            "POST",
        )

        body = request.data.decode("utf-8")

        self.assertIn(
            "data=",
            body,
        )

        self.assertIn(
            "signature=",
            body,
        )

        self.assertEqual(
            mock_urlopen.call_args.kwargs["timeout"],
            10,
        )

    @override_settings(
    LIQPAY_PUBLIC_KEY="sandbox_test_public",
    LIQPAY_PRIVATE_KEY="test_private_key",
    )
    @patch("apps.payments.services.liqpay.urlopen")
    def test_liqpay_refund_rejects_invalid_api_response(
        self,
        mock_urlopen,
    ):
        mocked_response = BytesIO(
            b"this-is-not-json"
        )

        mock_urlopen.return_value.__enter__.return_value = (
            mocked_response
        )

        with self.assertRaises(PaymentError):
            PaymentService._liqpay_create_refund(
                provider_order_id="test-order",
                amount=Decimal("5.00"),
            )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
    )
    def test_liqpay_payout_uses_destination_snapshot(
        self,
    ):
        _, teacher = make_teacher(
            email="snapshot-payout@example.com"
        )

        destination = (
            TeacherPayoutDestination.objects.create(
                teacher=teacher,
                provider="liqpay",
                destination_type=(
                    TeacherPayoutDestination
                    .TypeChoices
                    .BANK_ACCOUNT
                ),
                receiver_account="OLD-ACCOUNT",
                receiver_mfo="305299",
                receiver_okpo="1234567890",
                receiver_company="Old Name",
            )
        )

        payout = TeacherPayout.objects.create(
            teacher=teacher,
            destination=destination,
            destination_snapshot={
                "destination_type": (
                    "bank_account"
                ),
                "receiver_account": (
                    "OLD-ACCOUNT"
                ),
                "receiver_mfo": "305299",
                "receiver_okpo": "1234567890",
                "receiver_company": "Old Name",
            },
            amount=Decimal("10.00"),
            currency="UAH",
            provider=(
                TeacherPayout
                .ProviderChoices
                .LIQPAY
            ),
            idempotency_key=(
                "snapshot-payout-test"
            ),
        )

        destination.receiver_account = (
            "NEW-ACCOUNT"
        )

        destination.receiver_company = (
            "New Name"
        )

        destination.save(
            update_fields=[
                "receiver_account",
                "receiver_company",
                "updated_at",
            ]
        )

        request_data = (
            PaymentService
            ._liqpay_build_payout_request(
                payout=payout,
                client_ip="203.0.113.10",
            )
        )

        payload = (
            PaymentService
            ._liqpay_decode_data(
                request_data["data"]
            )
        )

        self.assertEqual(
            payload["receiver_account"],
            "OLD-ACCOUNT",
        )

        self.assertEqual(
            payload["receiver_company"],
            "Old Name",
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="sandbox_test_private",
    )
    def test_liqpay_payout_requires_client_ip(
        self,
    ):
        _, teacher = make_teacher(
            email="no-ip-payout@example.com"
        )

        payout = TeacherPayout.objects.create(
            teacher=teacher,
            destination_snapshot={
                "destination_type": (
                    "bank_account"
                ),
                "receiver_account": "TEST",
                "receiver_mfo": "305299",
                "receiver_okpo": "1234567890",
                "receiver_company": "Teacher",
            },
            amount=Decimal("10.00"),
            currency="UAH",
            provider=(
                TeacherPayout
                .ProviderChoices
                .LIQPAY
            ),
            idempotency_key=(
                "no-ip-payout-test"
            ),
        )

        with self.assertRaises(PaymentError):
            (
                PaymentService
                ._liqpay_build_payout_request(
                    payout=payout,
                    client_ip="",
                )
            )

    
def make_stripe_event(event_data: dict):
    return stripe.Event.construct_from(event_data, None)


class PaymentCheckoutTests(APITestCase):
    def setUp(self):
        self.teacher_user, self.teacher_profile = make_teacher(
            email="payments_teacher@example.com"
        )

        TeacherPayoutAccount.objects.create(
            teacher=self.teacher_profile,
            provider_account_id="acct_payments_teacher",
            status=TeacherPayoutAccount.StatusChoices.ACTIVE,
            details_submitted=True,
            charges_enabled=True,
            payouts_enabled=True,
        )
        self.course = make_course(
            self.teacher_profile,
            title="Paid Course",
            slug="paid-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.plan = make_pricing_plan(self.course, price="25.00")
        self.student_user, self.student_profile = make_student(
            email="payments_student@example.com"
        )
        self.cart = Cart.objects.create(student_profile=self.student_profile)
        CartItem.objects.create(
            cart=self.cart,
            course=self.course,
            pricing_plan=self.plan,
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
        LIQPAY_CHECKOUT_URL="https://www.liqpay.ua/api/3/checkout",
        LIQPAY_SERVER_URL="https://api.example.com/api/v1/payments/liqpay/callback/",
        LIQPAY_RESULT_URL="https://example.com/payment/result",
    )
    def test_start_liqpay_checkout_creates_provider_attempt(self):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount="25.00",
            gross_amount="25.00",
            platform_fee_amount="5.00",
            teacher_amount="20.00",
            currency="UAH",
            status=Payment.StatusChoices.PENDING,
            payment_method=Payment.MethodChoices.LIQPAY,
            description="Course payment",
        )

        payment, attempt, checkout = PaymentService._start_liqpay_checkout(
            payment=payment,
        )

        payment.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(
            payment.status,
            Payment.StatusChoices.PROCESSING,
        )
        self.assertEqual(
            payment.payment_method,
            Payment.MethodChoices.LIQPAY,
        )

        self.assertEqual(
            attempt.provider,
            Payment.MethodChoices.LIQPAY,
        )
        self.assertEqual(
            attempt.status,
            Payment.StatusChoices.PROCESSING,
        )

        self.assertEqual(
            attempt.provider_order_id,
            f"nexo-payment-{payment.id}-attempt-{attempt.id}",
        )

        self.assertEqual(
            checkout["checkout_url"],
            "https://www.liqpay.ua/api/3/checkout",
        )

        payload = PaymentService._liqpay_decode_data(
            checkout["data"]
        )

        self.assertEqual(
            payload["order_id"],
            attempt.provider_order_id,
        )
        self.assertEqual(payload["amount"], "25.00")
        self.assertEqual(payload["currency"], "UAH")
        self.assertEqual(payload["action"], "pay")
        self.assertEqual(payload["version"], 7)

        self.assertEqual(
            payload["server_url"],
            "https://api.example.com/api/v1/payments/liqpay/callback/",
        )
        self.assertEqual(
            payload["result_url"],
            "https://example.com/payment/result",
        )

        self.assertTrue(
            PaymentService._liqpay_verify_signature(
                data=checkout["data"],
                signature=checkout["signature"],
            )
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
        LIQPAY_SERVER_URL="https://api.example.com/liqpay/callback/",
    )
    @patch.object(
        PaymentService,
        "_liqpay_get_payment_status",
    )
    def test_liqpay_status_sync_completes_payment(
        self,
        mock_get_status,
    ):
        payment, attempt, _ = (
            PaymentService.create_liqpay_checkout(
                user=self.student_user,
            )
        )

        mock_get_status.return_value = {
            "public_key": "sandbox_test_public",
            "version": 7,
            "action": "pay",
            "order_id": attempt.provider_order_id,
            "amount": f"{payment.amount:.2f}",
            "currency": payment.currency,
            "status": "success",
            "payment_id": 555001,
            "transaction_id": 666001,
        }

        payment, provider_status = (
            PaymentService.sync_liqpay_payment_status(
                payment=payment,
            )
        )

        payment.refresh_from_db()
        attempt.refresh_from_db()
        payment.order.refresh_from_db()

        self.assertEqual(
            provider_status,
            "success",
        )

        self.assertEqual(
            payment.status,
            Payment.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            attempt.status,
            Payment.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            attempt.provider_status,
            "success",
        )

        self.assertEqual(
            attempt.provider_payment_id,
            "555001",
        )

        self.assertEqual(
            attempt.provider_transaction_id,
            "666001",
        )

        self.assertEqual(
            payment.order.status,
            Order.StatusChoices.PAID,
        )

        self.assertTrue(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
                access_status=(
                    Enrollment.AccessStatusChoices.ACTIVE
                ),
            ).exists()
        )
        PaymentService.sync_liqpay_payment_status(
            payment=payment,
        )

        self.assertEqual(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
            ).count(),
            1,
        )

        self.assertEqual(
            PaymentAttempt.objects.filter(
                payment=payment,
                provider=Payment.MethodChoices.LIQPAY,
            ).count(),
            1,
        )
            
    @override_settings(
    LIQPAY_PUBLIC_KEY="sandbox_test_public",
    LIQPAY_PRIVATE_KEY="test_private_key",
    LIQPAY_API_VERSION=7,
    LIQPAY_CHECKOUT_URL="https://www.liqpay.ua/api/3/checkout",
    LIQPAY_SERVER_URL="https://api.example.com/api/v1/payments/liqpay/callback/",
    LIQPAY_RESULT_URL="https://example.com/payment/result",
    )
    def test_liqpay_checkout_retry_reuses_payment_and_attempt(self):
        payment_1, attempt_1, checkout_1 = (
            PaymentService.create_liqpay_checkout(
                user=self.student_user,
            )
        )

        payment_2, attempt_2, checkout_2 = (
            PaymentService.create_liqpay_checkout(
                user=self.student_user,
            )
        )

        self.assertEqual(
            payment_1.id,
            payment_2.id,
        )

        self.assertEqual(
            attempt_1.id,
            attempt_2.id,
        )

        self.assertEqual(
            attempt_1.provider_order_id,
            attempt_2.provider_order_id,
        )

        self.assertEqual(
            checkout_1["data"],
            checkout_2["data"],
        )

        self.assertEqual(
            checkout_1["signature"],
            checkout_2["signature"],
        )

        self.assertEqual(
            Payment.objects.filter(
                payment_method=Payment.MethodChoices.LIQPAY,
            ).count(),
            1,
        )

        self.assertEqual(
            PaymentAttempt.objects.filter(
                provider=Payment.MethodChoices.LIQPAY,
            ).count(),
            1,
        )

        self.assertEqual(
            Order.objects.filter(
                user=self.student_user,
            ).count(),
            1,
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
        LIQPAY_CHECKOUT_URL="https://www.liqpay.ua/api/3/checkout",
        LIQPAY_SERVER_URL=(
            "https://api.example.com/"
            "api/v1/payments/liqpay/callback/"
        ),
        LIQPAY_RESULT_URL="https://example.com/payment/result",
    )
    def test_create_liqpay_checkout_from_cart(self):
        self.client.force_authenticate(
            user=self.student_user
        )

        response = self.client.post(
            reverse("payments-liqpay-checkout"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["checkout_url"],
            "https://www.liqpay.ua/api/3/checkout",
        )

        self.assertTrue(response.data["data"])
        self.assertTrue(response.data["signature"])
        self.assertTrue(response.data["provider_order_id"])

        payment = Payment.objects.get(
            pk=response.data["payment_id"]
        )

        self.assertEqual(
            payment.payment_method,
            Payment.MethodChoices.LIQPAY,
        )

        self.assertEqual(
            payment.status,
            Payment.StatusChoices.PROCESSING,
        )

        self.assertEqual(
            payment.order_id,
            response.data["order_id"],
        )

        attempt = PaymentAttempt.objects.get(
            payment=payment,
            provider=Payment.MethodChoices.LIQPAY,
        )

        self.assertEqual(
            attempt.provider_order_id,
            response.data["provider_order_id"],
        )

        self.assertEqual(
            attempt.status,
            Payment.StatusChoices.PROCESSING,
        )

        payload = PaymentService._liqpay_decode_data(
            response.data["data"]
        )

        self.assertEqual(
            payload["order_id"],
            attempt.provider_order_id,
        )

        self.assertEqual(
            payload["amount"],
            f"{payment.amount:.2f}",
        )

        self.assertEqual(
            payload["currency"],
            payment.currency,
        )

        self.assertEqual(
            payload["action"],
            "pay",
        )

        self.assertEqual(
            payload["server_url"],
            (
                "https://api.example.com/"
                "api/v1/payments/liqpay/callback/"
            ),
        )

        self.assertTrue(
            PaymentService._liqpay_verify_signature(
                data=response.data["data"],
                signature=response.data["signature"],
            )
        )


    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_SERVER_URL="https://api.example.com/liqpay/callback/",
    )
    def test_liqpay_checkout_requires_student(self):
        self.client.force_authenticate(
            user=self.teacher_user
        )

        response = self.client.post(
            reverse("payments-liqpay-checkout"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
        LIQPAY_CHECKOUT_URL="https://www.liqpay.ua/api/3/checkout",
        LIQPAY_SERVER_URL="https://api.example.com/liqpay/callback/",
        LIQPAY_RESULT_URL="https://example.com/payment/result",
    )
    def test_liqpay_success_callback_completes_payment(self):
        payment, attempt, _ = (
            PaymentService.create_liqpay_checkout(
                user=self.student_user,
            )
        )

        callback_payload = {
            "public_key": "sandbox_test_public",
            "version": 7,
            "action": "pay",
            "amount": f"{payment.amount:.2f}",
            "currency": payment.currency,
            "order_id": attempt.provider_order_id,
            "status": "success",
            "payment_id": 123456789,
            "transaction_id": 987654321,
        }

        data = PaymentService._liqpay_encode_payload(
            callback_payload
        )
        signature = PaymentService._liqpay_sign_data(data)

        PaymentService.handle_liqpay_callback(
            data=data,
            signature=signature,
        )

        payment.refresh_from_db()
        attempt.refresh_from_db()
        payment.order.refresh_from_db()

        self.assertEqual(
            payment.status,
            Payment.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            payment.order.status,
            Order.StatusChoices.PAID,
        )

        self.assertEqual(
            attempt.status,
            Payment.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            attempt.provider_status,
            "success",
        )

        self.assertEqual(
            attempt.provider_payment_id,
            "123456789",
        )

        self.assertEqual(
            attempt.provider_transaction_id,
            "987654321",
        )

        self.assertTrue(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
                access_status=Enrollment.AccessStatusChoices.ACTIVE,
                order_id=payment.order_id,
            ).exists()
        )

        self.assertFalse(
            CartItem.objects.filter(
                cart=self.cart,
                course=self.course,
            ).exists()
        )

        self.assertEqual(
            WebhookEvent.objects.filter(
                provider=WebhookEvent.ProviderChoices.LIQPAY,
            ).count(),
            1,
        )
        PaymentService.handle_liqpay_callback(
            data=data,
            signature=signature,
        )

        self.assertEqual(
            WebhookEvent.objects.filter(
                provider=WebhookEvent.ProviderChoices.LIQPAY,
            ).count(),
            1,
        )

        self.assertEqual(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
            ).count(),
            1,
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
    )
    def test_liqpay_callback_rejects_invalid_signature(self):
        payment, attempt, _ = (
            PaymentService.create_liqpay_checkout(
                user=self.student_user,
            )
        )

        payload = {
            "public_key": "sandbox_test_public",
            "version": 7,
            "action": "pay",
            "amount": f"{payment.amount:.2f}",
            "currency": payment.currency,
            "order_id": attempt.provider_order_id,
            "status": "success",
        }

        data = PaymentService._liqpay_encode_payload(
            payload
        )

        with self.assertRaises(PaymentError):
            PaymentService.handle_liqpay_callback(
                data=data,
                signature="fake-signature",
            )

        payment.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(
            payment.status,
            Payment.StatusChoices.PROCESSING,
        )

        self.assertEqual(
            attempt.status,
            Payment.StatusChoices.PROCESSING,
        )

        self.assertFalse(
            WebhookEvent.objects.filter(
                provider=WebhookEvent.ProviderChoices.LIQPAY,
            ).exists()
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
        LIQPAY_CHECKOUT_URL="https://www.liqpay.ua/api/3/checkout",
        LIQPAY_SERVER_URL="https://api.example.com/api/v1/payments/liqpay/callback/",
        LIQPAY_RESULT_URL="https://example.com/payment/result",
    )
    def test_liqpay_callback_endpoint_completes_payment(self):
        payment, attempt, _ = (
            PaymentService.create_liqpay_checkout(
                user=self.student_user,
            )
        )

        callback_payload = {
            "public_key": "sandbox_test_public",
            "version": 7,
            "action": "pay",
            "amount": f"{payment.amount:.2f}",
            "currency": payment.currency,
            "order_id": attempt.provider_order_id,
            "status": "success",
            "payment_id": 123456789,
            "transaction_id": 987654321,
        }

        data = PaymentService._liqpay_encode_payload(
            callback_payload
        )

        signature = PaymentService._liqpay_sign_data(
            data
        )

        body = urlencode(
            {
                "data": data,
                "signature": signature,
            }
        )

        response = self.client.post(
            reverse("liqpay-callback"),
            data=body,
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data,
            {"received": True},
        )

        payment.refresh_from_db()
        attempt.refresh_from_db()
        payment.order.refresh_from_db()

        self.assertEqual(
            payment.status,
            Payment.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            attempt.status,
            Payment.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            attempt.provider_status,
            "success",
        )

        self.assertEqual(
            payment.order.status,
            Order.StatusChoices.PAID,
        )

        self.assertTrue(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
                access_status=Enrollment.AccessStatusChoices.ACTIVE,
            ).exists()
        )

    @override_settings(
    LIQPAY_PUBLIC_KEY="sandbox_test_public",
    LIQPAY_PRIVATE_KEY="test_private_key",
    LIQPAY_API_VERSION=7,
    LIQPAY_CHECKOUT_URL="https://www.liqpay.ua/api/3/checkout",
    LIQPAY_SERVER_URL="https://api.example.com/api/v1/payments/liqpay/callback/",
    )
    def test_liqpay_callback_endpoint_rejects_invalid_signature(self):
        payment, attempt, _ = (
            PaymentService.create_liqpay_checkout(
                user=self.student_user,
            )
        )

        payload = {
            "public_key": "sandbox_test_public",
            "version": 7,
            "action": "pay",
            "amount": f"{payment.amount:.2f}",
            "currency": payment.currency,
            "order_id": attempt.provider_order_id,
            "status": "success",
        }

        data = PaymentService._liqpay_encode_payload(
            payload
        )

        body = urlencode(
            {
                "data": data,
                "signature": "definitely-not-valid",
            }
        )

        response = self.client.post(
            reverse("liqpay-callback"),
            data=body,
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        payment.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(
            payment.status,
            Payment.StatusChoices.PROCESSING,
        )

        self.assertEqual(
            attempt.status,
            Payment.StatusChoices.PROCESSING,
        )


    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
        LIQPAY_CHECKOUT_URL="https://www.liqpay.ua/api/3/checkout",
        LIQPAY_SERVER_URL="https://api.example.com/liqpay/callback/",
        LIQPAY_RESULT_URL="https://example.com/payment/result",
    )
    def test_create_second_installment_liqpay_checkout(self):
        self.plan.installment_count = 4
        self.plan.installment_amount = "6.25"
        self.plan.save(
            update_fields=[
                "installment_count",
                "installment_amount",
            ]
        )

        # First installment.
        first_payment, first_attempt, _ = (
            PaymentService.create_liqpay_checkout(
                user=self.student_user,
                payment_type=Order.PaymentTypeChoices.INSTALLMENTS,
                installments_count=4,
            )
        )

        first_payload = {
            "public_key": "sandbox_test_public",
            "version": 7,
            "action": "pay",
            "amount": f"{first_payment.amount:.2f}",
            "currency": first_payment.currency,
            "order_id": first_attempt.provider_order_id,
            "status": "success",
            "payment_id": 1001,
            "transaction_id": 2001,
        }

        first_data = PaymentService._liqpay_encode_payload(
            first_payload
        )

        first_signature = PaymentService._liqpay_sign_data(
            first_data
        )

        PaymentService.handle_liqpay_callback(
            data=first_data,
            signature=first_signature,
        )

        first_payment.refresh_from_db()

        order = first_payment.order
        order.refresh_from_db()

        self.assertEqual(
            order.status,
            Order.StatusChoices.PARTIALLY_PAID,
        )

        second_installment = order.installments.get(
            installment_number=2
        )

        self.assertEqual(
            second_installment.status,
            PaymentInstallment.StatusChoices.PENDING,
        )

        # Now start payment for installment #2.
        second_payment, second_attempt, checkout = (
            PaymentService.create_installment_liqpay_checkout(
                user=self.student_user,
                order_id=order.id,
                installment_id=second_installment.id,
            )
        )

        second_payment.refresh_from_db()
        second_attempt.refresh_from_db()
        second_installment.refresh_from_db()

        self.assertEqual(
            second_payment.payment_method,
            Payment.MethodChoices.LIQPAY,
        )

        self.assertEqual(
            second_payment.status,
            Payment.StatusChoices.PROCESSING,
        )

        self.assertEqual(
            second_payment.installment_id,
            second_installment.id,
        )

        self.assertEqual(
            str(second_payment.amount),
            "6.25",
        )

        self.assertEqual(
            second_installment.status,
            PaymentInstallment.StatusChoices.PROCESSING,
        )

        self.assertEqual(
            second_attempt.provider,
            Payment.MethodChoices.LIQPAY,
        )

        self.assertEqual(
            second_attempt.status,
            Payment.StatusChoices.PROCESSING,
        )

        payload = PaymentService._liqpay_decode_data(
            checkout["data"]
        )

        self.assertEqual(
            payload["order_id"],
            second_attempt.provider_order_id,
        )

        self.assertEqual(
            payload["amount"],
            "6.25",
        )
        retry_payment, retry_attempt, retry_checkout = (
            PaymentService.create_installment_liqpay_checkout(
                user=self.student_user,
                order_id=order.id,
                installment_id=second_installment.id,
            )
        )

        self.assertEqual(
            retry_payment.id,
            second_payment.id,
        )

        self.assertEqual(
            retry_attempt.id,
            second_attempt.id,
        )

        self.assertEqual(
            retry_attempt.provider_order_id,
            second_attempt.provider_order_id,
        )

        self.assertEqual(
            retry_checkout["data"],
            checkout["data"],
        )

        self.assertEqual(
            Payment.objects.filter(
                installment=second_installment,
                payment_method=Payment.MethodChoices.LIQPAY,
            ).count(),
            1,
        )

        self.assertEqual(
            PaymentAttempt.objects.filter(
                payment=second_payment,
                provider=Payment.MethodChoices.LIQPAY,
            ).count(),
            1,
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
        LIQPAY_CHECKOUT_URL="https://www.liqpay.ua/api/3/checkout",
        LIQPAY_SERVER_URL="https://api.example.com/liqpay/callback/",
        LIQPAY_RESULT_URL="https://example.com/payment/result",
    )
    def test_create_installment_liqpay_checkout_endpoint(self):
        self.plan.installment_count = 4
        self.plan.installment_amount = "6.25"
        self.plan.save(
            update_fields=[
                "installment_count",
                "installment_amount",
            ]
        )

        # Create installment order and pay installment #1.
        first_payment, first_attempt, _ = (
            PaymentService.create_liqpay_checkout(
                user=self.student_user,
                payment_type=Order.PaymentTypeChoices.INSTALLMENTS,
                installments_count=4,
            )
        )

        payload = {
            "public_key": "sandbox_test_public",
            "version": 7,
            "action": "pay",
            "amount": f"{first_payment.amount:.2f}",
            "currency": first_payment.currency,
            "order_id": first_attempt.provider_order_id,
            "status": "success",
            "payment_id": 1001,
            "transaction_id": 2001,
        }

        data = PaymentService._liqpay_encode_payload(payload)
        signature = PaymentService._liqpay_sign_data(data)

        PaymentService.handle_liqpay_callback(
            data=data,
            signature=signature,
        )

        first_payment.refresh_from_db()

        order = first_payment.order

        second_installment = order.installments.get(
            installment_number=2
        )

        self.client.force_authenticate(
            user=self.student_user
        )

        response = self.client.post(
            reverse(
                "orders-installment-liqpay-checkout",
                args=[
                    order.id,
                    second_installment.id,
                ],
            ),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["order_id"],
            order.id,
        )

        self.assertEqual(
            response.data["installment_id"],
            second_installment.id,
        )

        self.assertEqual(
            response.data["amount"],
            "6.25",
        )

        self.assertEqual(
            response.data["currency"],
            order.currency,
        )

        self.assertTrue(
            response.data["data"]
        )

        self.assertTrue(
            response.data["signature"]
        )

        self.assertTrue(
            response.data["provider_order_id"]
        )

        payment = Payment.objects.get(
            pk=response.data["payment_id"]
        )

        attempt = PaymentAttempt.objects.get(
            payment=payment,
            provider=Payment.MethodChoices.LIQPAY,
        )

        self.assertEqual(
            payment.payment_method,
            Payment.MethodChoices.LIQPAY,
        )

        self.assertEqual(
            payment.status,
            Payment.StatusChoices.PROCESSING,
        )

        self.assertEqual(
            payment.installment_id,
            second_installment.id,
        )

        self.assertEqual(
            attempt.provider_order_id,
            response.data["provider_order_id"],
        )

        decoded = PaymentService._liqpay_decode_data(
            response.data["data"]
        )

        self.assertEqual(
            decoded["order_id"],
            attempt.provider_order_id,
        )

        self.assertEqual(
            decoded["amount"],
            "6.25",
        )

        self.assertTrue(
            PaymentService._liqpay_verify_signature(
                data=response.data["data"],
                signature=response.data["signature"],
            )
        )


    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_API_VERSION=7,
        LIQPAY_SERVER_URL=(
            "https://api.example.com/liqpay/callback/"
        ),
    )
    @patch.object(
        PaymentService,
        "_liqpay_get_payment_status",
    )
    def test_liqpay_status_sync_endpoint(
        self,
        mock_get_status,
    ):
        payment, attempt, _ = (
            PaymentService.create_liqpay_checkout(
                user=self.student_user,
            )
        )

        mock_get_status.return_value = {
            "public_key": "sandbox_test_public",
            "version": 7,
            "action": "pay",
            "order_id": attempt.provider_order_id,
            "amount": f"{payment.amount:.2f}",
            "currency": payment.currency,
            "status": "success",
            "payment_id": 777001,
            "transaction_id": 888001,
        }

        self.client.force_authenticate(
            user=self.student_user
        )

        response = self.client.post(
            reverse(
                "payments-liqpay-status-sync"
            ),
            {
                "payment_id": payment.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["payment_id"],
            payment.id,
        )

        self.assertEqual(
            response.data["payment_status"],
            Payment.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            response.data["provider_status"],
            "success",
        )

        payment.refresh_from_db()
        attempt.refresh_from_db()

        self.assertEqual(
            payment.status,
            Payment.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            attempt.status,
            Payment.StatusChoices.SUCCEEDED,
        )

    @override_settings(
        LIQPAY_PUBLIC_KEY="sandbox_test_public",
        LIQPAY_PRIVATE_KEY="test_private_key",
        LIQPAY_SERVER_URL=(
            "https://api.example.com/liqpay/callback/"
        ),
    )
    def test_student_cannot_sync_another_students_liqpay_payment(
        self,
    ):
        payment, _, _ = (
            PaymentService.create_liqpay_checkout(
                user=self.student_user,
            )
        )

        other_user, _ = make_student(
            email="other-liqpay@example.com"
        )

        self.client.force_authenticate(
            user=other_user
        )

        response = self.client.post(
            reverse(
                "payments-liqpay-status-sync"
            ),
            {
                "payment_id": payment.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    @patch.object(PaymentService, "_create_stripe_session")
    def test_create_checkout_session_from_cart(self, create_stripe_session):
        create_stripe_session.return_value = SimpleNamespace(
            id="cs_test_123",
            url="https://checkout.stripe.test/session",
        )
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(reverse("payments-create-checkout-session"), {})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["checkout_url"], "https://checkout.stripe.test/session")
        payment = Payment.objects.get(pk=response.data["payment_id"])
        self.assertEqual(payment.status, Payment.StatusChoices.PROCESSING)
        self.assertEqual(str(payment.amount), "25.00")
        self.assertEqual(payment.currency, self.plan.currency)
        self.assertEqual(payment.stripe_session_id, "cs_test_123")
        self.assertIsNotNone(payment.order_id)
        self.assertEqual(payment.order.payment_type, Order.PaymentTypeChoices.FULL)
        self.assertEqual(payment.order.status, Order.StatusChoices.PENDING)
        self.assertEqual(payment.items.count(), 1)

        line_items = create_stripe_session.call_args.kwargs["line_items"]
        self.assertEqual(line_items[0]["price_data"]["currency"], self.plan.currency.lower())
        self.assertEqual(line_items[0]["price_data"]["unit_amount"], 2500)

    @patch.object(PaymentService, "_create_stripe_payment_intent")
    def test_create_payment_intent_from_cart(self, create_stripe_payment_intent):
        create_stripe_payment_intent.return_value = SimpleNamespace(
            id="pi_test_123",
            client_secret="pi_test_123_secret_abc",
        )
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(reverse("payments-create-payment-intent"), {})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["client_secret"], "pi_test_123_secret_abc")
        self.assertEqual(response.data["payment_intent_id"], "pi_test_123")
        payment = Payment.objects.get(pk=response.data["payment_id"])
        self.assertEqual(payment.status, Payment.StatusChoices.PROCESSING)
        self.assertEqual(str(payment.amount), "25.00")
        self.assertEqual(payment.currency, self.plan.currency)
        self.assertEqual(payment.stripe_payment_intent_id, "pi_test_123")
        self.assertEqual(payment.checkout_url, "")
        self.assertIsNotNone(payment.order_id)
        self.assertEqual(payment.order.payment_type, Order.PaymentTypeChoices.FULL)
        self.assertEqual(payment.items.count(), 1)

        intent_kwargs = create_stripe_payment_intent.call_args.kwargs
        self.assertEqual(intent_kwargs["payment"], payment)
        self.assertEqual(intent_kwargs["user"], self.student_user)

    def test_payment_intent_rejects_free_course(self):
        self.plan.price = "0.00"
        self.plan.save(update_fields=["price"])
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(reverse("payments-create-payment-intent"), {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Payment.objects.count(), 0)

    @patch.object(PaymentService, "_create_stripe_payment_intent")
    def test_create_payment_intent_from_selected_cart_items(self, create_stripe_payment_intent):
        other_course = make_course(
            self.teacher_profile,
            title="Selected Paid Course",
            slug="selected-paid-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        other_plan = make_pricing_plan(other_course, price="30.00")
        other_item = CartItem.objects.create(
            cart=self.cart,
            course=other_course,
            pricing_plan=other_plan,
        )
        create_stripe_payment_intent.return_value = SimpleNamespace(
            id="pi_selected_123",
            client_secret="pi_selected_123_secret_abc",
        )
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(
            reverse("payments-create-payment-intent"),
            {"selected_cart_item_ids": [other_item.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(pk=response.data["payment_id"])
        self.assertEqual(str(payment.amount), "30.00")
        self.assertEqual(payment.items.count(), 1)
        self.assertTrue(payment.items.filter(course=other_course).exists())
        self.assertFalse(payment.items.filter(course=self.course).exists())
        self.assertEqual(payment.order.metadata["cart_item_ids"], [other_item.id])

    @patch.object(PaymentService, "_create_stripe_payment_intent")
    def test_create_payment_intent_deletes_existing_processing_payment_for_cart_course(
        self,
        create_stripe_payment_intent,
    ):
        other_course = make_course(
            self.teacher_profile,
            title="Other Paid Course",
            slug="other-paid-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        other_plan = make_pricing_plan(other_course, price="30.00")
        stale_order = Order.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            total_amount="25.00",
            currency=self.plan.currency,
        )
        OrderItem.objects.create(
            order=stale_order,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )
        stale_payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            order=stale_order,
            amount=self.plan.price,
            currency=self.plan.currency,
            status=Payment.StatusChoices.PROCESSING,
            stripe_payment_intent_id="pi_stale",
        )
        PaymentItem.objects.create(
            payment=stale_payment,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )
        other_payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            amount=other_plan.price,
            currency=other_plan.currency,
            status=Payment.StatusChoices.PROCESSING,
            stripe_payment_intent_id="pi_other",
        )
        PaymentItem.objects.create(
            payment=other_payment,
            course=other_course,
            pricing_plan=other_plan,
            course_title=other_course.title,
            course_slug=other_course.slug,
            pricing_plan_kind=other_plan.delivery_format.format_type,
            unit_amount=other_plan.price,
            currency=other_plan.currency,
        )
        succeeded_payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            amount=self.plan.price,
            currency=self.plan.currency,
            status=Payment.StatusChoices.SUCCEEDED,
            stripe_payment_intent_id="pi_succeeded",
        )
        PaymentItem.objects.create(
            payment=succeeded_payment,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )
        create_stripe_payment_intent.return_value = SimpleNamespace(
            id="pi_new",
            client_secret="pi_new_secret_abc",
        )
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(reverse("payments-create-payment-intent"), {})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(Payment.objects.filter(pk=stale_payment.pk).exists())
        self.assertFalse(Order.objects.filter(pk=stale_order.pk).exists())
        self.assertTrue(Payment.objects.filter(pk=other_payment.pk).exists())
        self.assertTrue(Payment.objects.filter(pk=succeeded_payment.pk).exists())
        self.assertTrue(Payment.objects.filter(pk=response.data["payment_id"]).exists())

    @patch.object(PaymentService, "_create_stripe_session")
    def test_create_installment_checkout_session_from_cart(self, create_stripe_session):
        self.plan.installment_count = 4
        self.plan.installment_amount = "6.25"
        self.plan.save(update_fields=["installment_count", "installment_amount"])
        create_stripe_session.return_value = SimpleNamespace(
            id="cs_installment_123",
            url="https://checkout.stripe.test/installment",
        )
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(
            reverse("payments-create-checkout-session"),
            {
                "payment_type": Order.PaymentTypeChoices.INSTALLMENTS,
                "installments_count": 4,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.select_related("order", "installment").get(
            pk=response.data["payment_id"]
        )
        self.assertEqual(str(payment.amount), "6.25")
        self.assertEqual(payment.order.payment_type, Order.PaymentTypeChoices.INSTALLMENTS)
        self.assertEqual(str(payment.order.total_amount), "25.00")
        self.assertEqual(payment.order.installments.count(), 4)
        self.assertEqual(payment.installment.installment_number, 1)
        self.assertEqual(payment.installment.status, PaymentInstallment.StatusChoices.PROCESSING)

        line_items = create_stripe_session.call_args.kwargs["line_items"]
        self.assertEqual(line_items[0]["price_data"]["unit_amount"], 625)

    @patch.object(PaymentService, "_create_stripe_payment_intent")
    def test_create_installment_payment_intent(self, create_stripe_payment_intent):
        order = Order.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            total_amount="25.00",
            currency=self.plan.currency,
            payment_type=Order.PaymentTypeChoices.INSTALLMENTS,
            installments_count=4,
        )
        OrderItem.objects.create(
            order=order,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount="25.00",
            currency=self.plan.currency,
        )
        installment = PaymentInstallment.objects.create(
            order=order,
            installment_number=1,
            amount="6.25",
            currency=self.plan.currency,
            due_date=timezone.localdate(),
        )
        create_stripe_payment_intent.return_value = SimpleNamespace(
            id="pi_installment_123",
            client_secret="pi_installment_123_secret_abc",
        )
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(
            reverse(
                "orders-create-installment-payment-intent",
                args=[order.pk, installment.pk],
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["client_secret"], "pi_installment_123_secret_abc")
        self.assertEqual(response.data["installment_id"], installment.pk)
        payment = Payment.objects.select_related("installment").get(pk=response.data["payment_id"])
        installment.refresh_from_db()
        self.assertEqual(payment.status, Payment.StatusChoices.PROCESSING)
        self.assertEqual(payment.stripe_payment_intent_id, "pi_installment_123")
        self.assertEqual(str(payment.amount), "6.25")
        self.assertEqual(installment.status, PaymentInstallment.StatusChoices.PROCESSING)

    def test_create_checkout_session_rejects_empty_cart(self):
        self.cart.items.all().delete()
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(reverse("payments-create-checkout-session"), {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Cart is empty.")

    def test_checkout_completion_grants_enrollment_and_clears_cart_item(self):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            amount=self.plan.price,
            currency=self.plan.currency,
            status=Payment.StatusChoices.PROCESSING,
            stripe_session_id="cs_paid_123",
        )
        PaymentItem.objects.create(
            payment=payment,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )

        PaymentService.handle_checkout_session_completed(
            {
                "id": "cs_paid_123",
                "payment_status": "paid",
                "payment_intent": "pi_123",
                "customer": "cus_123",
            }
        )

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.StatusChoices.SUCCEEDED)
        self.assertEqual(payment.stripe_payment_intent_id, "pi_123")
        self.assertTrue(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
                access_status=Enrollment.AccessStatusChoices.ACTIVE,
                order_id=payment.id,
            ).exists()
        )
        self.assertFalse(
            CartItem.objects.filter(
                cart=self.cart,
                course=self.course,
            ).exists()
        )
        self.assertTrue(
            PaymentAttempt.objects.filter(
                payment=payment,
                status=Payment.StatusChoices.SUCCEEDED,
            ).exists()
        )

    def test_first_installment_completion_grants_access_and_partially_pays_order(self):
        order = Order.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            total_amount="25.00",
            currency=self.plan.currency,
            payment_type=Order.PaymentTypeChoices.INSTALLMENTS,
            installments_count=4,
        )
        OrderItem.objects.create(
            order=order,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount="25.00",
            currency=self.plan.currency,
        )
        installment = PaymentInstallment.objects.create(
            order=order,
            installment_number=1,
            amount="6.25",
            currency=self.plan.currency,
            due_date=timezone.localdate(),
            status=PaymentInstallment.StatusChoices.PROCESSING,
        )
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            order=order,
            installment=installment,
            amount="6.25",
            currency=self.plan.currency,
            status=Payment.StatusChoices.PROCESSING,
            stripe_session_id="cs_installment_paid",
        )
        PaymentItem.objects.create(
            payment=payment,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount="25.00",
            currency=self.plan.currency,
        )

        PaymentService.handle_checkout_session_completed(
            {
                "id": "cs_installment_paid",
                "payment_status": "paid",
                "payment_intent": "pi_installment_paid",
                "customer": "cus_installment_paid",
            }
        )

        payment.refresh_from_db()
        order.refresh_from_db()
        installment.refresh_from_db()
        self.assertEqual(payment.status, Payment.StatusChoices.SUCCEEDED)
        self.assertEqual(order.status, Order.StatusChoices.PARTIALLY_PAID)
        self.assertEqual(installment.status, PaymentInstallment.StatusChoices.PAID)
        self.assertTrue(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
                access_status=Enrollment.AccessStatusChoices.ACTIVE,
                order_id=order.id,
            ).exists()
        )
        self.assertFalse(
            CartItem.objects.filter(
                cart=self.cart,
                course=self.course,
            ).exists()
        )

    @patch.object(PaymentService, "construct_stripe_event")
    def test_webhook_ignores_unhandled_stripe_event(self, construct_stripe_event):
        construct_stripe_event.return_value = make_stripe_event(
            {
                "id": "evt_charge_succeeded",
                "type": "charge.succeeded",
                "data": {"object": {"id": "ch_123"}},
            }
        )

        response = self.client.post(
            reverse("stripe-webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test-signature",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"received": True})

    @patch.object(PaymentService, "construct_stripe_event")
    def test_root_webhook_alias_accepts_stripe_events(self, construct_stripe_event):
        construct_stripe_event.return_value = make_stripe_event(
            {
                "id": "evt_root_alias_charge",
                "type": "charge.succeeded",
                "data": {"object": {"id": "ch_root_alias"}},
            }
        )

        response = self.client.post(
            "/webhook",
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test-signature",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"received": True})

    def test_serialize_stripe_event_object_from_sdk(self):
        event = make_stripe_event(
            {
                "id": "evt_sdk_object",
                "type": "charge.succeeded",
                "data": {"object": {"id": "ch_sdk_123"}},
            }
        )

        event_data = PaymentService.serialize_stripe_object(event)

        self.assertEqual(event_data["id"], "evt_sdk_object")
        self.assertEqual(event_data["data"]["object"]["id"], "ch_sdk_123")

    @patch.object(PaymentService, "construct_stripe_event")
    def test_webhook_checkout_completion_grants_access(self, construct_stripe_event):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            amount=self.plan.price,
            currency=self.plan.currency,
            status=Payment.StatusChoices.PROCESSING,
            stripe_session_id="cs_webhook_123",
        )
        PaymentItem.objects.create(
            payment=payment,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )

        construct_stripe_event.return_value = {
            "id": "evt_checkout_completed",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_webhook_123",
                    "payment_status": "paid",
                    "payment_intent": "pi_webhook_123",
                    "customer": "cus_webhook_123",
                }
            },
        }

        response = self.client.post(
            reverse("stripe-webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test-signature",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.StatusChoices.SUCCEEDED)
        self.assertTrue(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
                access_status=Enrollment.AccessStatusChoices.ACTIVE,
            ).exists()
        )

    @patch.object(PaymentService, "construct_stripe_event")
    def test_webhook_payment_intent_completion_grants_access(self, construct_stripe_event):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            amount=self.plan.price,
            currency=self.plan.currency,
            status=Payment.StatusChoices.PROCESSING,
            stripe_session_id="cs_pi_123",
        )
        PaymentItem.objects.create(
            payment=payment,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )
        construct_stripe_event.return_value = make_stripe_event(
            {
                "id": "evt_payment_intent_succeeded",
                "type": "payment_intent.succeeded",
                "data": {
                    "object": {
                        "id": "pi_webhook_456",
                        "status": "succeeded",
                        "customer": "cus_webhook_456",
                        "metadata": {"payment_id": str(payment.id)},
                    }
                },
            }
        )

        response = self.client.post(
            reverse("stripe-webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test-signature",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.StatusChoices.SUCCEEDED)
        self.assertEqual(payment.stripe_payment_intent_id, "pi_webhook_456")
        self.assertTrue(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
                access_status=Enrollment.AccessStatusChoices.ACTIVE,
            ).exists()
        )

    @patch.object(PaymentService, "_retrieve_stripe_payment_intent")
    def test_sync_payment_intent_status_grants_access(self, retrieve_payment_intent):
        order = Order.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            total_amount=self.plan.price,
            currency=self.plan.currency,
        )
        OrderItem.objects.create(
            order=order,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            order=order,
            amount=self.plan.price,
            currency=self.plan.currency,
            status=Payment.StatusChoices.PROCESSING,
            stripe_payment_intent_id="pi_sync_123",
        )
        PaymentItem.objects.create(
            payment=payment,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )
        retrieve_payment_intent.return_value = {
            "id": "pi_sync_123",
            "status": "succeeded",
            "amount": 2500,
            "currency": self.plan.currency.lower(),
            "customer": "cus_sync_123",
            "metadata": {"payment_id": str(payment.id)},
        }
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(
            reverse("payments-sync-payment-intent-status"),
            {
                "payment_id": payment.id,
                "payment_intent_id": "pi_sync_123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment_status"], Payment.StatusChoices.SUCCEEDED)
        self.assertEqual(response.data["order_status"], Order.StatusChoices.PAID)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, Payment.StatusChoices.SUCCEEDED)
        self.assertEqual(payment.stripe_customer_id, "cus_sync_123")
        self.assertEqual(order.status, Order.StatusChoices.PAID)
        self.assertTrue(
            Enrollment.objects.filter(
                student_profile=self.student_profile,
                course=self.course,
                access_status=Enrollment.AccessStatusChoices.ACTIVE,
            ).exists()
        )
        self.assertFalse(
            CartItem.objects.filter(
                cart=self.cart,
                course=self.course,
            ).exists()
        )

    @patch.object(PaymentService, "_retrieve_stripe_payment_intent")
    def test_sync_payment_intent_status_rejects_mismatched_metadata(
        self,
        retrieve_payment_intent,
    ):
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            amount=self.plan.price,
            currency=self.plan.currency,
            status=Payment.StatusChoices.PROCESSING,
            stripe_payment_intent_id="pi_bad_metadata",
        )
        PaymentItem.objects.create(
            payment=payment,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )
        retrieve_payment_intent.return_value = {
            "id": "pi_bad_metadata",
            "status": "succeeded",
            "amount": 2500,
            "currency": self.plan.currency.lower(),
            "customer": "cus_bad_metadata",
            "metadata": {"payment_id": str(payment.id + 1)},
        }
        self.client.force_authenticate(user=self.student_user)

        response = self.client.post(
            reverse("payments-sync-payment-intent-status"),
            {
                "payment_id": payment.id,
                "payment_intent_id": "pi_bad_metadata",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.StatusChoices.PROCESSING)

@override_settings(
    LIQPAY_PUBLIC_KEY="sandbox_test_public",
    LIQPAY_PRIVATE_KEY="test_private_key",
    LIQPAY_API_VERSION=7,
)
class LiqPayRefundTests(APITestCase):
    def setUp(self):
        self.teacher_user, self.teacher_profile = make_teacher(
            email="liqpay-refund-teacher@example.com"
        )

        self.student_user, self.student_profile = make_student(
            email="liqpay-refund-student@example.com"
        )

        self.payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            teacher=self.teacher_profile,
            amount=Decimal("100.00"),
            gross_amount=Decimal("100.00"),
            platform_fee_amount=Decimal("20.00"),
            teacher_amount=Decimal("80.00"),
            currency="UAH",
            payment_method=Payment.MethodChoices.LIQPAY,
            status=Payment.StatusChoices.SUCCEEDED,
            processed_at=timezone.now(),
        )

        self.attempt = PaymentAttempt.objects.create(
            payment=self.payment,
            provider=Payment.MethodChoices.LIQPAY,
            provider_order_id="nexo-payment-refund-test",
            provider_payment_id="123456",
            provider_status="success",
            status=Payment.StatusChoices.SUCCEEDED,
            processed_at=timezone.now(),
        )

    @patch.object(LiqPayService, "_liqpay_create_refund")
    def test_full_liqpay_refund_succeeds(
        self,
        mock_refund,
    ):
        mock_refund.return_value = {
            "result": "ok",
            "wait_amount": False,
            "payment_id": 123456,
            "status": "reversed",
        }

        PaymentService.refund_payment(
            payment=self.payment,
            amount=Decimal("100.00"),
            reason="Customer request",
        )

        self.payment.refresh_from_db()

        refund = Refund.objects.get(
            payment=self.payment
        )

        self.assertEqual(
            refund.provider,
            Payment.MethodChoices.LIQPAY,
        )

        self.assertEqual(
            refund.status,
            Refund.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            refund.provider_status,
            "reversed",
        )

        self.assertEqual(
            refund.provider_reference,
            "123456",
        )

        self.assertEqual(
            self.payment.status,
            Payment.StatusChoices.REFUNDED,
        )

        mock_refund.assert_called_once_with(
            provider_order_id=self.attempt.provider_order_id,
            amount=Decimal("100.00"),
        )

    @patch.object(LiqPayService, "_liqpay_create_refund")
    def test_partial_liqpay_refund_keeps_payment_succeeded(
        self,
        mock_refund,
    ):
        mock_refund.return_value = {
            "result": "ok",
            "wait_amount": False,
            "payment_id": 123456,
            "status": "reversed",
        }

        PaymentService.refund_payment(
            payment=self.payment,
            amount=Decimal("25.00"),
        )

        self.payment.refresh_from_db()

        refund = Refund.objects.get(
            payment=self.payment
        )

        self.assertEqual(
            refund.status,
            Refund.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            refund.amount,
            Decimal("25.00"),
        )

        self.assertEqual(
            self.payment.status,
            Payment.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            PaymentService.refunded_total(
                self.payment
            ),
            Decimal("25.00"),
        )

    @patch.object(LiqPayService, "_liqpay_create_refund")
    def test_pending_liqpay_refund_reserves_amount(
        self,
        mock_refund,
    ):
        mock_refund.return_value = {
            "result": "ok",
            "wait_amount": True,
            "payment_id": 123456,
            "status": "processing",
        }

        PaymentService.refund_payment(
            payment=self.payment,
            amount=Decimal("80.00"),
        )

        refund = Refund.objects.get(
            payment=self.payment
        )

        self.assertEqual(
            refund.status,
            Refund.StatusChoices.PENDING,
        )

        self.assertEqual(
            refund.provider_status,
            "processing",
        )

        self.assertEqual(
            PaymentService.refundable_remaining(
                self.payment
            ),
            Decimal("20.00"),
        )

        with self.assertRaises(RefundError):
            PaymentService.refund_payment(
                payment=self.payment,
                amount=Decimal("21.00"),
            )

    @patch.object(
        LiqPayService,
        "_liqpay_get_payment_status",
    )
    @patch.object(
        LiqPayService,
        "_liqpay_create_refund",
    )
    def test_uncertain_full_liqpay_refund_reconciles_to_success(
        self,
        mock_create_refund,
        mock_get_status,
    ):
        mock_create_refund.side_effect = (
            PaymentError(
                "Connection lost."
            )
        )

        with self.assertRaises(
            PaymentError
        ):
            PaymentService.refund_payment(
                payment=self.payment,
                amount=Decimal("100.00"),
            )

        refund = Refund.objects.get(
            payment=self.payment
        )

        self.assertEqual(
            refund.status,
            Refund.StatusChoices.PENDING,
        )

        self.assertEqual(
            refund.provider_status,
            "request_uncertain",
        )

        mock_get_status.return_value = {
            "result": "ok",
            "public_key": (
                "sandbox_test_public"
            ),
            "version": 7,
            "action": "pay",
            "order_id": (
                self.attempt.provider_order_id
            ),
            "amount": "100.00",
            "currency": "UAH",
            "status": "reversed",
            "payment_id": 123456,
            "transaction_id": 123456,
        }

        PaymentService.reconcile_liqpay_refund(
            refund=refund
        )

        refund.refresh_from_db()
        self.payment.refresh_from_db()

        self.assertEqual(
            refund.status,
            Refund.StatusChoices.SUCCEEDED,
        )

        self.assertEqual(
            refund.provider_status,
            "reversed",
        )

        self.assertFalse(
            refund.metadata[
                "request_uncertain"
            ]
        )

        self.assertTrue(
            refund.metadata[
                "reconciled"
            ]
        )

        self.assertEqual(
            self.payment.status,
            Payment.StatusChoices.REFUNDED,
        )

        ledger = (
            TeacherLedgerEntry.objects.get(
                refund=refund,
                entry_type=(
                    TeacherLedgerEntry
                    .TypeChoices
                    .REFUND
                ),
            )
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry
            .StatusChoices
            .POSTED,
        )

    @patch.object(
        LiqPayService,
        "_liqpay_get_payment_status",
    )
    @patch.object(
        LiqPayService,
        "_liqpay_create_refund",
    )
    def test_uncertain_liqpay_refund_payment_success_stays_pending(
        self,
        mock_create_refund,
        mock_get_status,
    ):
        mock_create_refund.side_effect = (
            PaymentError(
                "Connection lost."
            )
        )

        with self.assertRaises(
            PaymentError
        ):
            PaymentService.refund_payment(
                payment=self.payment,
                amount=Decimal("50.00"),
            )

        refund = Refund.objects.get(
            payment=self.payment
        )

        mock_get_status.return_value = {
            "result": "ok",
            "public_key": (
                "sandbox_test_public"
            ),
            "version": 7,
            "action": "pay",
            "order_id": (
                self.attempt.provider_order_id
            ),
            "amount": "100.00",
            "currency": "UAH",
            "status": "success",
            "payment_id": 123456,
        }

        PaymentService.reconcile_liqpay_refund(
            refund=refund
        )

        refund.refresh_from_db()

        self.assertEqual(
            refund.status,
            Refund.StatusChoices.PENDING,
        )

        ledger = (
            TeacherLedgerEntry.objects.get(
                refund=refund,
                entry_type=(
                    TeacherLedgerEntry
                    .TypeChoices
                    .REFUND
                ),
            )
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry
            .StatusChoices
            .PENDING,
        )

        self.assertEqual(
            PaymentService.refundable_remaining(
                self.payment
            ),
            Decimal("50.00"),
        )

    @patch.object(
        LiqPayService,
        "_liqpay_create_refund",
    )
    def test_second_refund_is_blocked_while_first_is_pending(
        self,
        mock_create_refund,
    ):
        mock_create_refund.return_value = {
            "result": "ok",
            "status": "processing",
            "wait_amount": True,
            "payment_id": 123456,
        }

        PaymentService.refund_payment(
            payment=self.payment,
            amount=Decimal("30.00"),
        )

        with self.assertRaises(
            RefundError
        ):
            PaymentService.refund_payment(
                payment=self.payment,
                amount=Decimal("20.00"),
            )

        self.assertEqual(
            Refund.objects.filter(
                payment=self.payment
            ).count(),
            1,
        )

    @patch.object(LiqPayService, "_liqpay_create_refund")
    def test_failed_liqpay_refund_releases_reserved_amount(
        self,
        mock_refund,
    ):
        mock_refund.return_value = {
            "result": "error",
            "status": "failure",
        }

        with self.assertRaises(PaymentError):
            PaymentService.refund_payment(
                payment=self.payment,
                amount=Decimal("60.00"),
            )

        refund = Refund.objects.get(
            payment=self.payment
        )

        self.assertEqual(
            refund.status,
            Refund.StatusChoices.FAILED,
        )

        self.assertEqual(
            PaymentService.refundable_remaining(
                self.payment
            ),
            Decimal("100.00"),
        )

    @patch.object(
        LiqPayService,
        "_liqpay_create_refund",
    )
    def test_liqpay_refund_transport_error_stays_pending(
        self,
        mock_refund,
    ):
        mock_refund.side_effect = PaymentError(
            "Could not connect to LiqPay API."
        )

        with self.assertRaises(PaymentError):
            PaymentService.refund_payment(
                payment=self.payment,
                amount=Decimal("50.00"),
            )

        refund = Refund.objects.get(
            payment=self.payment
        )

        self.assertEqual(
            refund.status,
            Refund.StatusChoices.PENDING,
        )

        self.assertEqual(
            refund.provider_status,
            "request_uncertain",
        )

        self.assertTrue(
            refund.metadata[
                "request_uncertain"
            ]
        )

        self.assertIsNone(
            refund.processed_at
        )

        self.assertEqual(
            refund.metadata[
                "provider_order_id"
            ],
            self.attempt.provider_order_id,
        )

        ledger = (
            TeacherLedgerEntry.objects
            .get(
                refund=refund,
                entry_type=(
                    TeacherLedgerEntry
                    .TypeChoices
                    .REFUND
                ),
            )
        )

        self.assertEqual(
            ledger.status,
            TeacherLedgerEntry
            .StatusChoices
            .PENDING,
        )

        # 50 UAH is still reserved for a refund
        # whose provider outcome is unknown.
        self.assertEqual(
            PaymentService.refundable_remaining(
                self.payment
            ),
            Decimal("50.00"),
        )
        with self.assertRaises(RefundError):
            PaymentService.refund_payment(
                payment=self.payment,
                amount=Decimal("50.01"),
            )


class OverdueInstallmentTests(APITestCase):
    """Access is suspended lazily, the moment it's checked (course page /
    lesson open -- both go through EnrollmentService.student_has_course_access /
    get_access_status), not by any scheduled job."""

    def setUp(self):
        _, self.teacher_profile = make_teacher(email="overdue_teacher@example.com")
        self.course = make_course(
            self.teacher_profile,
            title="Overdue Course",
            slug="overdue-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.plan = make_pricing_plan(
            self.course,
            price="25.00",
            installment_count=4,
            installment_amount="6.25",
        )
        self.student_user, self.student_profile = make_student(
            email="overdue_student@example.com"
        )
        self.order = Order.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            total_amount="25.00",
            currency=self.plan.currency,
            payment_type=Order.PaymentTypeChoices.INSTALLMENTS,
            installments_count=4,
        )
        OrderItem.objects.create(
            order=self.order,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount="6.25",
            currency=self.plan.currency,
        )
        self.overdue_installment = PaymentInstallment.objects.create(
            order=self.order,
            installment_number=2,
            amount="6.25",
            currency=self.plan.currency,
            due_date=timezone.localdate() - timezone.timedelta(days=3),
            status=PaymentInstallment.StatusChoices.PENDING,
        )
        self.enrollment = Enrollment.objects.create(
            student_profile=self.student_profile,
            course=self.course,
            order_id=self.order.id,
            access_status=Enrollment.AccessStatusChoices.ACTIVE,
        )

    def test_access_check_suspends_and_notifies_on_overdue_installment(self):
        has_access = EnrollmentService.student_has_course_access(
            self.student_profile, self.course,
        )

        self.assertFalse(has_access)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.access_status, Enrollment.AccessStatusChoices.SUSPENDED)
        notification = Notification.objects.get(
            recipient=self.student_user, type=Notification.TypeChoices.PAYMENT_OVERDUE,
        )
        self.assertIn(self.course.title, notification.body)

    def test_access_check_is_idempotent_for_already_suspended_enrollment(self):
        EnrollmentService.student_has_course_access(self.student_profile, self.course)
        EnrollmentService.student_has_course_access(self.student_profile, self.course)

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.student_user,
                type=Notification.TypeChoices.PAYMENT_OVERDUE,
            ).count(),
            1,
        )

    def test_access_check_ignores_future_and_paid_installments(self):
        self.overdue_installment.due_date = timezone.localdate() + timezone.timedelta(days=3)
        self.overdue_installment.save(update_fields=["due_date"])

        has_access = EnrollmentService.student_has_course_access(
            self.student_profile, self.course,
        )

        self.assertTrue(has_access)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.access_status, Enrollment.AccessStatusChoices.ACTIVE)
        self.assertFalse(
            Notification.objects.filter(type=Notification.TypeChoices.PAYMENT_OVERDUE).exists()
        )

    def test_get_access_status_also_triggers_the_lazy_suspend(self):
        status_value = EnrollmentService.get_access_status(self.student_user, self.course)

        self.assertEqual(status_value, Enrollment.AccessStatusChoices.SUSPENDED)

    def test_paying_overdue_installment_restores_suspended_access(self):
        EnrollmentService.student_has_course_access(self.student_profile, self.course)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.access_status, Enrollment.AccessStatusChoices.SUSPENDED)

        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            order=self.order,
            installment=self.overdue_installment,
            amount="6.25",
            currency=self.plan.currency,
            status=Payment.StatusChoices.PROCESSING,
            stripe_session_id="cs_overdue_paid",
        )
        PaymentItem.objects.create(
            payment=payment,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount="6.25",
            currency=self.plan.currency,
        )

        PaymentService.handle_checkout_session_completed(
            {
                "id": "cs_overdue_paid",
                "payment_status": "paid",
                "payment_intent": "pi_overdue_paid",
                "customer": "cus_overdue_paid",
            }
        )

        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.access_status, Enrollment.AccessStatusChoices.ACTIVE)
        self.assertTrue(
            EnrollmentService.student_has_course_access(self.student_profile, self.course)
        )


class OrderInvoiceTests(APITestCase):
    def setUp(self):
        _, teacher_profile = make_teacher(email="invoice_teacher@example.com")
        self.course = make_course(
            teacher_profile,
            title="Invoice Course",
            slug="invoice-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.plan = make_pricing_plan(self.course, price="25.00")
        self.student_user, self.student_profile = make_student(
            email="invoice_student@example.com"
        )
        self.order = Order.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            total_amount=self.plan.price,
            currency=self.plan.currency,
        )
        OrderItem.objects.create(
            order=self.order,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )

    def test_student_can_download_own_order_invoice(self):
        self.client.force_authenticate(user=self.student_user)

        response = self.client.get(reverse("orders-invoice", args=[self.order.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="invoice-{self.order.id}.pdf"',
        )
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_student_cannot_download_another_students_invoice(self):
        other_user, _ = make_student(email="other_invoice_student@example.com")
        self.client.force_authenticate(user=other_user)

        response = self.client.get(reverse("orders-invoice", args=[self.order.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_order_invoice_returns_404(self):
        self.client.force_authenticate(user=self.student_user)

        response = self.client.get(reverse("orders-invoice", args=[999999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PaymentReceiptTests(APITestCase):
    def setUp(self):
        _, teacher_profile = make_teacher(email="receipt_teacher@example.com")
        self.course = make_course(
            teacher_profile,
            title="Receipt Course",
            slug="receipt-course",
            status=Course.StatusChoices.PUBLISHED,
        )
        self.plan = make_pricing_plan(self.course, price="25.00")
        self.student_user, self.student_profile = make_student(
            email="receipt_student@example.com"
        )
        self.order = Order.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            total_amount=self.plan.price,
            currency=self.plan.currency,
            status=Order.StatusChoices.PAID,
            completed_at=timezone.now(),
        )
        OrderItem.objects.create(
            order=self.order,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )
        self.payment = self._create_payment(Payment.StatusChoices.SUCCEEDED)

    def _create_payment(self, status_value: str) -> Payment:
        payment = Payment.objects.create(
            user=self.student_user,
            student_profile=self.student_profile,
            order=self.order,
            amount=self.plan.price,
            currency=self.plan.currency,
            status=status_value,
            stripe_payment_intent_id="pi_receipt_123",
            processed_at=timezone.now() if status_value == Payment.StatusChoices.SUCCEEDED else None,
        )
        PaymentItem.objects.create(
            payment=payment,
            course=self.course,
            pricing_plan=self.plan,
            course_title=self.course.title,
            course_slug=self.course.slug,
            pricing_plan_kind=self.plan.delivery_format.format_type,
            unit_amount=self.plan.price,
            currency=self.plan.currency,
        )
        return payment

    def test_student_can_download_receipt_for_own_successful_payment(self):
        self.client.force_authenticate(user=self.student_user)

        response = self.client.get(reverse("payments-receipt", args=[self.payment.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="receipt-{self.order.id}-{self.payment.id}.pdf"',
        )
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_student_cannot_download_another_students_receipt(self):
        other_user, _ = make_student(email="other_receipt_student@example.com")
        self.client.force_authenticate(user=other_user)

        response = self.client.get(reverse("payments-receipt", args=[self.payment.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_pending_payment_receipt_returns_conflict(self):
        pending_payment = self._create_payment(Payment.StatusChoices.PENDING)
        self.client.force_authenticate(user=self.student_user)

        response = self.client.get(reverse("payments-receipt", args=[pending_payment.pk]))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["detail"], "Receipt is available only after successful payment.")

    def test_failed_payment_receipt_returns_conflict(self):
        failed_payment = self._create_payment(Payment.StatusChoices.FAILED)
        self.client.force_authenticate(user=self.student_user)

        response = self.client.get(reverse("payments-receipt", args=[failed_payment.pk]))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["detail"], "Receipt is available only after successful payment.")

    def test_missing_payment_receipt_returns_404(self):
        self.client.force_authenticate(user=self.student_user)

        response = self.client.get(reverse("payments-receipt", args=[999999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TeacherPayoutConnectTests(APITestCase):
    def setUp(self):
        self.teacher_user, self.teacher = make_teacher(email="connect@example.com")
        self.student_user, _ = make_student(email="connect-student@example.com")

    def test_old_teacher_and_student_permissions(self):
        self.client.force_authenticate(self.teacher_user)
        response = self.client.get(reverse("teacher-payout-status"))
        self.assertEqual(response.data["status"], "not_configured")
        self.client.force_authenticate(self.student_user)
        self.assertEqual(self.client.post(reverse("teacher-payout-onboarding")).status_code, 403)

    @patch.object(PaymentService, "_load_stripe")
    def test_onboarding_reuses_connected_account(self, load_stripe):
        from types import SimpleNamespace
        load_stripe.return_value = SimpleNamespace(
            Account=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(id="acct_123", country="US")),
            AccountLink=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(url="https://connect.test/setup")),
        )
        self.client.force_authenticate(self.teacher_user)
        self.assertEqual(self.client.post(reverse("teacher-payout-onboarding")).status_code, 200)
        self.assertEqual(self.client.post(reverse("teacher-payout-onboarding")).status_code, 200)
        from apps.payments.models import TeacherPayoutAccount
        self.assertEqual(TeacherPayoutAccount.objects.filter(teacher=self.teacher).count(), 1)

    def test_account_updated_activates_account_idempotently(self):
        from apps.payments.models import TeacherPayoutAccount, WebhookEvent
        payout = TeacherPayoutAccount.objects.create(teacher=self.teacher, provider_account_id="acct_active")
        event = WebhookEvent.objects.create(provider="stripe", event_id="evt_account", event_type="account.updated", data={
            "id": "evt_account", "type": "account.updated", "data": {"object": {
                "id": "acct_active", "country": "US", "details_submitted": True,
                "charges_enabled": True, "payouts_enabled": True, "requirements": {},
            }}})
        PaymentService.process_webhook_event(event)
        PaymentService.process_webhook_event(event)
        payout.refresh_from_db()
        self.assertEqual(payout.status, "active")
