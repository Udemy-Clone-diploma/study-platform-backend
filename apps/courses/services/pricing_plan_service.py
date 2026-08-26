from decimal import Decimal

from django.db import IntegrityError, transaction

from apps.courses.exceptions import DuplicatePricingKindError
from apps.courses.models import Course, PricingPlan


class PricingPlanService:
    @staticmethod
    @transaction.atomic
    def create_for_course(course: Course, validated_data: dict) -> PricingPlan:
        try:
            return PricingPlan.objects.create(course=course, **validated_data)
        except IntegrityError as exc:
            raise DuplicatePricingKindError(
                f"Course already has a pricing plan with kind={validated_data.get('kind')}."
            ) from exc

    @staticmethod
    @transaction.atomic
    def update_plan(plan: PricingPlan, validated_data: dict) -> PricingPlan:
        for field, value in validated_data.items():
            setattr(plan, field, value)
        plan.save()
        return plan

    @staticmethod
    def validate_installment_fields(
        validated_data: dict, instance: PricingPlan | None = None
    ) -> None:
        """Cross-field validation that installment_count and installment_amount
        either both appear (with sensible values) or both stay null.
        """
        count = validated_data.get(
            "installment_count",
            getattr(instance, "installment_count", None),
        )
        amount = validated_data.get(
            "installment_amount",
            getattr(instance, "installment_amount", None),
        )
        price = validated_data.get("price", getattr(instance, "price", None))

        if count is None and amount is None:
            return

        if count is None or amount is None:
            raise ValueError(
                "installment_count and installment_amount must both be set or both be null."
            )

        if count < 2:
            raise ValueError("installment_count must be at least 2.")
        if amount <= 0:
            raise ValueError("installment_amount must be greater than 0.")
        if price is not None and Decimal(count) * Decimal(amount) < price:
            raise ValueError("Sum of installments must cover the plan price.")
