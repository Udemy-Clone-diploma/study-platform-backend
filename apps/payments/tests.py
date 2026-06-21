from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.cart.models import Cart, CartItem
from apps.courses.models import Course
from apps.courses.tests._factories import make_course, make_pricing_plan, make_teacher
from apps.enrollments.models import Enrollment
from apps.enrollments.tests._factories import make_student
from apps.payments.models import (
    Order,
    OrderItem,
    Payment,
    PaymentAttempt,
    PaymentInstallment,
    PaymentItem,
)
from apps.payments.services import PaymentService


def make_stripe_event(event_data: dict):
    return stripe.Event.construct_from(event_data, None)


class PaymentCheckoutTests(APITestCase):
    def setUp(self):
        _, self.teacher_profile = make_teacher(email="payments_teacher@example.com")
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=other_plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
            pricing_plan_kind=self.plan.kind,
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
