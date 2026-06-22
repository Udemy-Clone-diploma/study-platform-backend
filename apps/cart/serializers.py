from rest_framework import serializers

from apps.cart.models import Cart, CartItem
from apps.common.files import absolute_media_url
from apps.courses.models import Cohort, Course, PricingPlan


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
            "subtotal",
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
        return f"{plan.installment_amount:.2f}"


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

    def validate(self, attrs):
        course = attrs["course"]
        pricing_plan = attrs.get("pricing_plan")
        cohort = attrs.get("cohort")

        if pricing_plan is not None and pricing_plan.delivery_format.course_id != course.id:
            raise serializers.ValidationError(
                {"pricing_plan_id": "Pricing plan does not belong to this course."}
            )

        if pricing_plan is None:
            from apps.courses.models import PricingPlan as _PricingPlan
            pricing_plan = _PricingPlan.objects.filter(delivery_format__course=course).order_by("price", "id").first()
            if pricing_plan is not None:
                attrs["pricing_plan"] = pricing_plan

        if cohort is not None:
            if cohort.course_id != course.id:
                raise serializers.ValidationError(
                    {"cohort_id": "Cohort does not belong to this course."}
                )
            if not cohort.is_enrollment_open:
                raise serializers.ValidationError(
                    {"cohort_id": "This cohort is not open for enrollment."}
                )
            if cohort.group_size is not None and cohort.members.count() >= cohort.group_size:
                raise serializers.ValidationError(
                    {"cohort_id": "This cohort is full."}
                )

        return attrs


class CartItemRemoveSerializer(serializers.Serializer):
    course_id = serializers.IntegerField(min_value=1)
