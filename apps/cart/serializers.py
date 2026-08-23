from django.utils import timezone
from rest_framework import serializers

from apps.cart.models import Cart, CartItem
from apps.common.files import absolute_media_url
from apps.courses.models import Cohort, Course, CourseDeliveryFormat, PricingPlan
from apps.courses.services import DeliveryFormatService
from apps.schedule.models import ScheduleSlot


class CartItemSerializer(serializers.ModelSerializer):
    course = serializers.SerializerMethodField()
    course_id = serializers.IntegerField(read_only=True)
    pricing_plan_id = serializers.IntegerField(read_only=True)
    pricing_plan_kind = serializers.SerializerMethodField()
    installment_count = serializers.SerializerMethodField()
    installment_amount = serializers.SerializerMethodField()
    currency = serializers.CharField(read_only=True, allow_null=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    original_unit_price = serializers.SerializerMethodField()
    schedule_slots = serializers.SerializerMethodField()
    cohort = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "course_id",
            "course",
            "pricing_plan_id",
            "pricing_plan_kind",
            "installment_count",
            "installment_amount",
            "currency",
            "unit_price",
            "original_unit_price",
            "subtotal",
            "schedule_slots",
            "cohort",
            "added_at",
        ]

    def get_course(self, obj: CartItem) -> dict:
        request = self.context.get("request")
        return {
            "id": obj.course_id,
            "title": obj.course.title,
            "slug": obj.course.slug,
            "image": absolute_media_url(obj.course.image, request),
            "level": obj.course.level,
            "price": f"{obj.unit_price:.2f}",
            "currency": obj.currency,
        }

    def get_pricing_plan_kind(self, obj: CartItem) -> str | None:
        plan = obj.selected_pricing_plan
        if plan is None:
            return None
        return plan.delivery_format.format_type

    def get_installment_count(self, obj: CartItem) -> int | None:
        plan = obj.selected_pricing_plan
        return plan.installment_count if plan else None

    def get_installment_amount(self, obj: CartItem) -> str | None:
        plan = obj.selected_pricing_plan
        if plan is None or plan.installment_amount is None:
            return None
        return f"{plan.final_installment_amount:.2f}"

    def get_original_unit_price(self, obj: CartItem) -> str | None:
        plan = obj.selected_pricing_plan
        if plan is None or plan.final_price == plan.price:
            return None
        return f"{plan.price:.2f}"

    def get_schedule_slots(self, obj: CartItem) -> list[dict]:
        return [
            {
                "id": slot.id,
                "day_of_week": slot.day_of_week,
                "start_time": slot.start_time.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M"),
            }
            for slot in obj.schedule_slots.all()
        ]

    def get_cohort(self, obj: CartItem) -> dict | None:
        if not obj.cohort_id:
            return None
        return {
            "id": obj.cohort.id,
            "name": obj.cohort.name,
            "start_date": obj.cohort.start_date.isoformat() if obj.cohort.start_date else None,
        }


class CartSerializer(serializers.ModelSerializer):
    student_profile_id = serializers.IntegerField(read_only=True)
    items = CartItemSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    total_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    currency = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = Cart
        fields = [
            "id",
            "student_profile_id",
            "items",
            "items_count",
            "total_price",
            "currency",
            "created_at",
            "updated_at",
        ]


class CartItemAddSerializer(serializers.Serializer):
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.select_related("teacher_profile__user", "category")
        .prefetch_related("delivery_formats", "delivery_formats__pricing", "tags"),
        source="course",
        write_only=True,
    )
    pricing_plan_id = serializers.PrimaryKeyRelatedField(
        queryset=PricingPlan.objects.select_related("delivery_format__course"),
        source="pricing_plan",
        required=False,
        allow_null=True,
        write_only=True,
    )
    cohort_id = serializers.PrimaryKeyRelatedField(
        queryset=Cohort.objects.select_related("course"),
        source="cohort",
        required=False,
        allow_null=True,
        write_only=True,
    )
    schedule_slot_ids = serializers.PrimaryKeyRelatedField(
        queryset=ScheduleSlot.objects.select_related("delivery_format__course"),
        source="schedule_slots",
        many=True,
        required=False,
        write_only=True,
    )

    def validate(self, attrs):
        course = attrs["course"]
        pricing_plan = attrs.get("pricing_plan")
        cohort = attrs.get("cohort")
        schedule_slots = attrs.get("schedule_slots")

        if pricing_plan is not None and pricing_plan.delivery_format.course_id != course.id:
            raise serializers.ValidationError(
                {"pricing_plan_id": "Pricing plan does not belong to this course."}
            )

        if pricing_plan is None:
            from apps.courses.models import PricingPlan as _PricingPlan
            pricing_plan = _PricingPlan.objects.filter(delivery_format__course=course).order_by("price", "id").first()
            if pricing_plan is not None:
                attrs["pricing_plan"] = pricing_plan

        delivery_format = pricing_plan.delivery_format if pricing_plan is not None else None
        if (
            delivery_format is not None
            and delivery_format.format_type == CourseDeliveryFormat.FormatType.GROUP
        ):
            if not DeliveryFormatService.accepts_enrollment_on(
                delivery_format,
                timezone.localdate(),
            ):
                raise serializers.ValidationError(
                    {"cohort_id": "Enrollment for this group format has closed."}
                )
        elif cohort is not None:
            raise serializers.ValidationError(
                {"cohort_id": "A cohort can only be selected for the group format."}
            )

        if cohort is not None:
            if cohort.course_id != course.id:
                raise serializers.ValidationError(
                    {"cohort_id": "Cohort does not belong to this course."}
                )
            if (
                delivery_format is not None
                and cohort.delivery_format_id is not None
                and cohort.delivery_format_id != delivery_format.id
            ):
                raise serializers.ValidationError(
                    {"cohort_id": "Cohort does not belong to the selected group format."}
                )
            if not cohort.is_enrollment_open:
                raise serializers.ValidationError(
                    {"cohort_id": "This cohort is not open for enrollment."}
                )
            if (
                cohort.enrollment_deadline is not None
                and cohort.enrollment_deadline < timezone.localdate()
            ):
                raise serializers.ValidationError(
                    {"cohort_id": "Enrollment for this cohort has closed."}
                )
            if cohort.group_size is not None and cohort.members.count() >= cohort.group_size:
                raise serializers.ValidationError(
                    {"cohort_id": "This cohort is full."}
                )

        if schedule_slots:
            if len(schedule_slots) not in (2, 3):
                raise serializers.ValidationError(
                    {"schedule_slot_ids": "Select 2 or 3 available time slots."}
                )
            for slot in schedule_slots:
                if slot.delivery_format.course_id != course.id:
                    raise serializers.ValidationError(
                        {"schedule_slot_ids": "Time slot does not belong to this course."}
                    )
                if slot.delivery_format.format_type != CourseDeliveryFormat.FormatType.INDIVIDUAL:
                    raise serializers.ValidationError(
                        {"schedule_slot_ids": "Time slot is not part of the individual coaching format."}
                    )
                if not slot.is_available:
                    raise serializers.ValidationError(
                        {"schedule_slot_ids": "One of the selected time slots is no longer available."}
                    )

        return attrs


class CartItemRemoveSerializer(serializers.Serializer):
    course_id = serializers.IntegerField(min_value=1)
