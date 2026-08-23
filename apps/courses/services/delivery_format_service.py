from decimal import Decimal

from django.db import IntegrityError, transaction

from apps.courses.exceptions import DuplicateDeliveryFormatError
from apps.courses.models import Course, CourseDeliveryFormat, PricingPlan


class DeliveryFormatService:
    @staticmethod
    @transaction.atomic
    def create_for_course(course: Course, validated_data: dict) -> CourseDeliveryFormat:
        pricing_data = validated_data.pop("pricing", None)
        try:
            fmt = CourseDeliveryFormat.objects.create(course=course, **validated_data)
        except IntegrityError as exc:
            raise DuplicateDeliveryFormatError(
                f"Course already has a delivery format of type "
                f"'{validated_data.get('format_type')}'."
            ) from exc
        if pricing_data:
            DeliveryFormatService._validate_installment(pricing_data)
            PricingPlan.objects.create(delivery_format=fmt, **pricing_data)
        return fmt

    @staticmethod
    @transaction.atomic
    def update_format(fmt: CourseDeliveryFormat, validated_data: dict) -> CourseDeliveryFormat:
        pricing_data = validated_data.pop("pricing", None)
        for field, value in validated_data.items():
            setattr(fmt, field, value)
        fmt.save()
        if pricing_data is not None:
            pricing = getattr(fmt, "pricing", None)
            if pricing:
                DeliveryFormatService._validate_installment(pricing_data, instance=pricing)
                for field, value in pricing_data.items():
                    setattr(pricing, field, value)
                pricing.save()
            else:
                DeliveryFormatService._validate_installment(pricing_data)
                PricingPlan.objects.create(delivery_format=fmt, **pricing_data)
        return fmt

    @staticmethod
    def _validate_installment(
        validated_data: dict, instance: PricingPlan | None = None,
    ) -> None:
        count = validated_data.get(
            "installment_count", getattr(instance, "installment_count", None),
        )
        amount = validated_data.get(
            "installment_amount", getattr(instance, "installment_amount", None),
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
        if price is not None and Decimal(count) * Decimal(amount) < Decimal(str(price)):
            raise ValueError("Sum of installments must cover the plan price.")
