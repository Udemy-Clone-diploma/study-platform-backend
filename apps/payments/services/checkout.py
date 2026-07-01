from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.cart.models import CartItem
from apps.cart.services import CartService
from apps.courses.models import Course
from apps.enrollments.services import EnrollmentService
from apps.payments.models import (
    Order,
    OrderItem,
    Payment,
    PaymentInstallment,
    PaymentItem,
)
from apps.users.models import StudentProfile, User

from .base import PaymentBaseService
from .exceptions import PaymentError


class CheckoutService(PaymentBaseService):
    @classmethod
    def _cart_items_for_checkout(
        cls,
        student_profile: StudentProfile,
        selected_cart_item_ids: list[int] | None = None,
    ) -> list[CartItem]:
        cart = CartService.get_or_create_cart(student_profile)
        queryset = cart.items.select_related(
            "course",
            "pricing_plan",
            "pricing_plan__delivery_format",
            "course__teacher_profile__user",
            "cohort",
        ).prefetch_related("course__delivery_formats__pricing")

        if selected_cart_item_ids is not None:
            unique_item_ids = list(dict.fromkeys(selected_cart_item_ids))
            if not unique_item_ids:
                raise PaymentError("Select at least one cart item.")

            queryset = queryset.filter(id__in=unique_item_ids)
            items = list(queryset)
            if len(items) != len(unique_item_ids):
                raise PaymentError("Selected cart item was not found.")
            return items

        return list(queryset)

    @staticmethod
    def _validate_cart_items(student_profile: StudentProfile, items: list[CartItem]) -> str:
        if not items:
            raise PaymentError("Cart is empty.")

        currencies = {item.currency for item in items if item.currency}
        if len(currencies) != 1:
            raise PaymentError("Cart must contain payable items in a single currency.")

        for item in items:
            if item.selected_pricing_plan is None:
                raise PaymentError(f"Course '{item.course.title}' has no pricing plan.")
            if item.course.status != Course.StatusChoices.PUBLISHED or item.course.is_deleted:
                raise PaymentError(f"Course '{item.course.title}' is not available for purchase.")
            if EnrollmentService.student_has_course_access(student_profile, item.course):
                raise PaymentError(f"Student already has access to '{item.course.title}'.")

        return currencies.pop()

    @classmethod
    def _delete_processing_payments_for_cart_items(
        cls,
        *,
        student_profile: StudentProfile,
        items: list[CartItem],
    ) -> None:
        course_ids = [item.course_id for item in items]
        if not course_ids:
            return

        stale_payment_ids = list(
            Payment.objects.filter(
                student_profile=student_profile,
                status=Payment.StatusChoices.PROCESSING,
                items__course_id__in=course_ids,
            )
            .values_list("id", flat=True)
            .distinct()
        )
        if not stale_payment_ids:
            return

        stale_payment_ids = list(
            Payment.objects.select_for_update()
            .filter(id__in=stale_payment_ids)
            .values_list("id", flat=True)
        )

        stale_order_ids = list(
            Payment.objects.filter(
                id__in=stale_payment_ids,
                order__status=Order.StatusChoices.PENDING,
            ).values_list("order_id", flat=True)
        )

        Payment.objects.filter(id__in=stale_payment_ids).delete()

        if stale_order_ids:
            Order.objects.filter(
                id__in=stale_order_ids,
                student_profile=student_profile,
                status=Order.StatusChoices.PENDING,
                payments__isnull=True,
            ).delete()

    @classmethod
    def _resolve_checkout_amounts(
        cls,
        *,
        items: list[CartItem],
        payment_type: str,
        installments_count: int | None,
    ) -> tuple[int, dict[int, Decimal], list[Decimal]]:
        if payment_type == Order.PaymentTypeChoices.FULL:
            item_totals = {item.id: cls._decimal_money(item.subtotal) for item in items}
            total = cls._decimal_money(sum(item_totals.values(), Decimal("0.00")))
            return 1, item_totals, [total]

        if payment_type != Order.PaymentTypeChoices.INSTALLMENTS:
            raise PaymentError("Unsupported payment type.")

        configured_counts = set()
        installment_amounts_by_item: dict[int, Decimal] = {}

        for item in items:
            plan = item.selected_pricing_plan
            if (
                plan is None
                or plan.installment_count is None
                or plan.installment_amount is None
            ):
                raise PaymentError(
                    "Installment checkout is available only for pricing plans with installment terms."
                )

            configured_counts.add(plan.installment_count)
            installment_amounts_by_item[item.id] = cls._decimal_money(plan.installment_amount)

        if len(configured_counts) != 1:
            raise PaymentError("All cart items must use the same installment count.")

        configured_count = configured_counts.pop()
        if installments_count is not None and installments_count != configured_count:
            raise PaymentError("Requested installment count does not match the pricing plan.")

        count = installments_count or configured_count
        if count < 2:
            raise PaymentError("Installment count must be at least 2.")

        item_totals = {
            item_id: cls._decimal_money(installment_amount * count)
            for item_id, installment_amount in installment_amounts_by_item.items()
        }
        installment_amount = cls._decimal_money(
            sum(installment_amounts_by_item.values(), Decimal("0.00"))
        )
        return count, item_totals, [installment_amount for _ in range(count)]

    @classmethod
    def _create_order_from_cart(
        cls,
        *,
        user: User,
        student_profile: StudentProfile,
        items: list[CartItem],
        currency: str,
        payment_type: str,
        installments_count: int | None,
    ) -> tuple[Order, list[PaymentInstallment]]:
        count, item_totals, installment_amounts = cls._resolve_checkout_amounts(
            items=items,
            payment_type=payment_type,
            installments_count=installments_count,
        )
        total_amount = cls._decimal_money(sum(item_totals.values(), Decimal("0.00")))
        if total_amount <= Decimal("0.00"):
            raise PaymentError("Order total must be greater than zero.")

        cart_total = cls._decimal_money(sum((item.subtotal for item in items), Decimal("0.00")))
        order = Order.objects.create(
            user=user,
            student_profile=student_profile,
            total_amount=total_amount,
            currency=currency,
            status=Order.StatusChoices.PENDING,
            payment_type=payment_type,
            installments_count=count,
            metadata={
                "cart_item_ids": [item.id for item in items],
                "cart_total": f"{cart_total:.2f}",
            },
        )

        created_order_items = OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    course=item.course,
                    pricing_plan=item.selected_pricing_plan,
                    cohort=item.cohort,
                    course_title=item.course.title,
                    course_slug=item.course.slug,
                    pricing_plan_kind=item.selected_pricing_plan.delivery_format.format_type,
                    unit_amount=item_totals[item.id],
                    currency=currency,
                )
                for item in items
            ]
        )
        for order_item, cart_item in zip(created_order_items, items):
            slot_ids = list(cart_item.schedule_slots.values_list("id", flat=True))
            if slot_ids:
                order_item.schedule_slots.set(slot_ids)

        installments = []
        if payment_type == Order.PaymentTypeChoices.INSTALLMENTS:
            today = timezone.localdate()
            for index, amount in enumerate(installment_amounts, start=1):
                installments.append(
                    PaymentInstallment.objects.create(
                        order=order,
                        installment_number=index,
                        amount=amount,
                        currency=currency,
                        due_date=cls._add_months(today, index - 1),
                    )
                )

        return order, installments

    @staticmethod
    def _payment_description(order: Order, installment: PaymentInstallment | None = None) -> str:
        if installment is None:
            return "Course cart checkout"
        return (
            f"Course cart installment {installment.installment_number}"
            f" of {order.installments_count}"
        )

    @staticmethod
    def _snapshot_payment_items(payment: Payment, order: Order) -> None:
        order_items = list(
            order.items.select_related("course", "pricing_plan", "cohort").prefetch_related(
                "schedule_slots"
            )
        )
        created_payment_items = PaymentItem.objects.bulk_create(
            [
                PaymentItem(
                    payment=payment,
                    course=item.course,
                    pricing_plan=item.pricing_plan,
                    cohort=item.cohort,
                    course_title=item.course_title,
                    course_slug=item.course_slug,
                    pricing_plan_kind=item.pricing_plan_kind,
                    unit_amount=item.unit_amount,
                    currency=item.currency,
                )
                for item in order_items
            ]
        )
        for payment_item, order_item in zip(created_payment_items, order_items):
            slot_ids = list(order_item.schedule_slots.values_list("id", flat=True))
            if slot_ids:
                payment_item.schedule_slots.set(slot_ids)

    @classmethod
    def _create_payment_for_order(
        cls,
        *,
        order: Order,
        installment: PaymentInstallment | None = None,
    ) -> Payment:
        amount = installment.amount if installment is not None else order.total_amount
        payment = Payment.objects.create(
            user=order.user,
            student_profile=order.student_profile,
            order=order,
            installment=installment,
            amount=amount,
            currency=order.currency,
            status=Payment.StatusChoices.PENDING,
            description=cls._payment_description(order, installment),
            metadata={
                "order_id": order.id,
                "installment_id": installment.id if installment else None,
                "payment_type": order.payment_type,
            },
        )
        cls._snapshot_payment_items(payment, order)
        return payment

    @classmethod
    def _stripe_line_items_for_payment(cls, payment: Payment) -> list[dict]:
        if payment.order_id is None:
            return [
                {
                    "price_data": {
                        "currency": payment.currency.lower(),
                        "product_data": {"name": payment.description or f"Payment #{payment.id}"},
                        "unit_amount": cls._to_minor_units(payment.amount),
                    },
                    "quantity": 1,
                }
            ]

        order = payment.order
        installment = payment.installment
        line_items = []

        for item in order.items.select_related("course", "pricing_plan"):
            amount = item.unit_amount
            name = item.course_title
            if installment is not None:
                amount = cls._decimal_money(item.unit_amount / order.installments_count)
                name = (
                    f"{item.course_title} - installment "
                    f"{installment.installment_number} of {order.installments_count}"
                )

            line_items.append(
                {
                    "price_data": {
                        "currency": item.currency.lower(),
                        "product_data": {
                            "name": name,
                            "metadata": {
                                "course_id": str(item.course_id or ""),
                                "pricing_plan_id": str(item.pricing_plan_id or ""),
                                "order_id": str(order.id),
                                "installment_id": str(installment.id if installment else ""),
                            },
                        },
                        "unit_amount": cls._to_minor_units(amount),
                    },
                    "quantity": 1,
                }
            )

        return line_items

    @classmethod
    def _start_stripe_checkout(
        cls,
        *,
        payment: Payment,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> Payment:
        session = cls._create_stripe_session(
            payment=payment,
            user=payment.user,
            line_items=cls._stripe_line_items_for_payment(payment),
            success_url=success_url or cls._default_success_url(),
            cancel_url=cancel_url or cls._default_cancel_url(),
        )
        payment.mark_as_processing(session_id=session.id, checkout_url=session.url)
        if payment.installment_id:
            payment.installment.mark_as_processing()
        return payment

    @classmethod
    def _start_stripe_payment_intent(cls, *, payment: Payment) -> tuple[Payment, str]:
        payment_intent = cls._create_stripe_payment_intent(
            payment=payment,
            user=payment.user,
        )
        payment.mark_intent_as_processing(payment_intent_id=payment_intent.id)
        if payment.installment_id:
            payment.installment.mark_as_processing()
        return payment, payment_intent.client_secret

    @classmethod
    @transaction.atomic
    def create_checkout_session(
        cls,
        *,
        user: User,
        success_url: str | None = None,
        cancel_url: str | None = None,
        selected_cart_item_ids: list[int] | None = None,
        payment_type: str = Order.PaymentTypeChoices.FULL,
        installments_count: int | None = None,
    ) -> Payment:
        student_profile = cls._student_profile_for_user(user)
        items = cls._cart_items_for_checkout(
            student_profile,
            selected_cart_item_ids=selected_cart_item_ids,
        )
        currency = cls._validate_cart_items(student_profile, items)
        cls._delete_processing_payments_for_cart_items(
            student_profile=student_profile,
            items=items,
        )
        order, installments = cls._create_order_from_cart(
            user=user,
            student_profile=student_profile,
            items=items,
            currency=currency,
            payment_type=payment_type,
            installments_count=installments_count,
        )
        installment = installments[0] if installments else None
        payment = cls._create_payment_for_order(order=order, installment=installment)
        return cls._start_stripe_checkout(
            payment=payment,
            success_url=success_url,
            cancel_url=cancel_url,
        )

    @classmethod
    @transaction.atomic
    def create_payment_intent(
        cls,
        *,
        user: User,
        selected_cart_item_ids: list[int] | None = None,
        payment_type: str = Order.PaymentTypeChoices.FULL,
        installments_count: int | None = None,
    ) -> tuple[Payment, str]:
        student_profile = cls._student_profile_for_user(user)
        items = cls._cart_items_for_checkout(
            student_profile,
            selected_cart_item_ids=selected_cart_item_ids,
        )
        currency = cls._validate_cart_items(student_profile, items)
        cls._delete_processing_payments_for_cart_items(
            student_profile=student_profile,
            items=items,
        )
        order, installments = cls._create_order_from_cart(
            user=user,
            student_profile=student_profile,
            items=items,
            currency=currency,
            payment_type=payment_type,
            installments_count=installments_count,
        )
        installment = installments[0] if installments else None
        payment = cls._create_payment_for_order(order=order, installment=installment)
        return cls._start_stripe_payment_intent(payment=payment)

    @classmethod
    def _get_payable_installment(
        cls,
        *,
        student_profile: StudentProfile,
        order_id: int,
        installment_id: int,
    ) -> PaymentInstallment:
        installment = (
            PaymentInstallment.objects.select_for_update()
            .select_related("order", "order__user", "order__student_profile")
            .filter(
                pk=installment_id,
                order_id=order_id,
                order__student_profile=student_profile,
            )
            .first()
        )
        if installment is None:
            raise PaymentError("Installment was not found.")

        order = installment.order
        if order.status in {Order.StatusChoices.PAID, Order.StatusChoices.CANCELED}:
            raise PaymentError("This order cannot accept more payments.")
        if order.payment_type != Order.PaymentTypeChoices.INSTALLMENTS:
            raise PaymentError("This order is not an installment order.")
        if installment.status == PaymentInstallment.StatusChoices.PAID:
            raise PaymentError("This installment is already paid.")

        has_unpaid_previous = order.installments.filter(
            installment_number__lt=installment.installment_number,
        ).exclude(status=PaymentInstallment.StatusChoices.PAID).exists()
        if has_unpaid_previous:
            raise PaymentError("Previous installments must be paid first.")

        return installment

    @classmethod
    @transaction.atomic
    def create_installment_checkout_session(
        cls,
        *,
        user: User,
        order_id: int,
        installment_id: int,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> Payment:
        student_profile = cls._student_profile_for_user(user)
        installment = cls._get_payable_installment(
            student_profile=student_profile,
            order_id=order_id,
            installment_id=installment_id,
        )
        order = installment.order

        existing_payment = installment.payments.filter(
            status=Payment.StatusChoices.PROCESSING,
        ).exclude(checkout_url="").order_by("-created_at").first()
        if existing_payment is not None:
            return existing_payment

        payment = cls._create_payment_for_order(order=order, installment=installment)
        return cls._start_stripe_checkout(
            payment=payment,
            success_url=success_url,
            cancel_url=cancel_url,
        )

    @classmethod
    @transaction.atomic
    def create_installment_payment_intent(
        cls,
        *,
        user: User,
        order_id: int,
        installment_id: int,
    ) -> tuple[Payment, str]:
        student_profile = cls._student_profile_for_user(user)
        installment = cls._get_payable_installment(
            student_profile=student_profile,
            order_id=order_id,
            installment_id=installment_id,
        )

        existing_payment = installment.payments.filter(
            status=Payment.StatusChoices.PROCESSING,
        ).exclude(stripe_payment_intent_id="").order_by("-created_at").first()
        if existing_payment is not None:
            client_secret = cls._retrieve_stripe_payment_intent_client_secret(
                existing_payment.stripe_payment_intent_id
            )
            return existing_payment, client_secret

        payment = cls._create_payment_for_order(
            order=installment.order,
            installment=installment,
        )
        return cls._start_stripe_payment_intent(payment=payment)
