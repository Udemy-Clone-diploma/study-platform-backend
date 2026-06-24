from django.db import transaction
from django.db.models import Prefetch
from rest_framework import serializers
from rest_framework.exceptions import NotFound

from apps.cart.models import Cart, CartItem
from apps.cart.serializers import (
    CartItemAddSerializer,
    CartItemRemoveSerializer,
    CartSerializer,
)
from apps.courses.models import Course, PricingPlan
from apps.enrollments.services import EnrollmentService
from apps.users.models import StudentProfile, User


class CartService:
    @staticmethod
    def get_items_queryset():
        return CartItem.objects.select_related(
            "course",
            "course__teacher_profile__user",
            "course__category",
            "pricing_plan",
            "pricing_plan__delivery_format",
            "cohort",
        ).prefetch_related("course__delivery_formats", "course__delivery_formats__pricing", "course__tags")

    @classmethod
    def get_base_queryset(cls):
        return Cart.objects.select_related("student_profile__user").prefetch_related(
            Prefetch("items", queryset=cls.get_items_queryset())
        )

    @staticmethod
    def serialize_cart(cart: Cart, context: dict | None = None) -> dict:
        return CartSerializer(cart, context=context or {}).data

    @staticmethod
    def validate_add_item_data(data: dict, context: dict | None = None) -> dict:
        serializer = CartItemAddSerializer(data=data, context=context or {})
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @staticmethod
    def validate_remove_item_data(data: dict, context: dict | None = None) -> dict:
        serializer = CartItemRemoveSerializer(data=data, context=context or {})
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @staticmethod
    def _student_profile_for_user(user: User) -> StudentProfile:
        try:
            return user.student_profile
        except StudentProfile.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"detail": "Student profile is required for cart operations."}
            ) from exc

    @classmethod
    def _refresh_cart(cls, cart: Cart) -> Cart:
        return cls.get_base_queryset().get(pk=cart.pk)

    @classmethod
    @transaction.atomic
    def get_or_create_cart(cls, student_profile: StudentProfile) -> Cart:
        cart, _ = Cart.objects.get_or_create(student_profile=student_profile)
        return cls._refresh_cart(cart)

    @classmethod
    def get_current_cart(cls, user: User) -> Cart:
        student_profile = cls._student_profile_for_user(user)
        return cls.get_or_create_cart(student_profile)

    @staticmethod
    def _validate_course_is_available(course: Course) -> None:
        if course.status != Course.StatusChoices.PUBLISHED or course.is_deleted:
            raise serializers.ValidationError(
                {"course_id": "Only published courses can be added to cart."}
            )

    @staticmethod
    def _validate_student_is_not_enrolled(
        student_profile: StudentProfile,
        course: Course,
    ) -> None:
        if EnrollmentService.student_has_course_access(student_profile, course):
            raise serializers.ValidationError(
                {"course_id": "Student already has access to this course."}
            )

    @staticmethod
    def _validate_cart_currency(cart: Cart, pricing_plan: PricingPlan | None) -> None:
        if pricing_plan is None:
            return

        existing_currencies = {
            item.currency
            for item in cart.items.select_related("pricing_plan", "course").prefetch_related(
                "course__delivery_formats", "course__delivery_formats__pricing"
            )
            if item.currency
        }
        if existing_currencies and pricing_plan.currency not in existing_currencies:
            raise serializers.ValidationError(
                {"pricing_plan_id": "Cart items must use the same currency."}
            )

    @classmethod
    @transaction.atomic
    def add_item(
        cls,
        cart: Cart,
        course: Course,
        pricing_plan: PricingPlan | None = None,
        cohort=None,
    ) -> Cart:
        cls._validate_course_is_available(course)
        cls._validate_student_is_not_enrolled(cart.student_profile, course)
        cls._validate_cart_currency(cart, pricing_plan)

        _, created = CartItem.objects.get_or_create(
            cart=cart,
            course=course,
            defaults={"pricing_plan": pricing_plan, "cohort": cohort},
        )
        if not created:
            raise serializers.ValidationError(
                {"course_id": "Course is already in cart."}
            )

        return cls._refresh_cart(cart)

    @classmethod
    def add_item_from_data(
        cls,
        data: dict,
        user: User,
        context: dict | None = None,
    ) -> dict:
        validated_data = cls.validate_add_item_data(data, context=context)
        cart = cls.get_current_cart(user)
        cart = cls.add_item(
            cart,
            validated_data["course"],
            validated_data.get("pricing_plan"),
            validated_data.get("cohort"),
        )
        return cls.serialize_cart(cart, context=context)

    @classmethod
    @transaction.atomic
    def remove_item(cls, cart: Cart, course_id: int) -> Cart:
        deleted_count, _ = cart.items.filter(course_id=course_id).delete()
        if deleted_count == 0:
            raise NotFound("Course is not in cart.")
        return cls._refresh_cart(cart)

    @classmethod
    def remove_item_from_data(
        cls,
        course_id: int,
        user: User,
        context: dict | None = None,
    ) -> dict:
        validated_data = cls.validate_remove_item_data(
            {"course_id": course_id},
            context=context,
        )
        cart = cls.get_current_cart(user)
        cart = cls.remove_item(cart, validated_data["course_id"])
        return cls.serialize_cart(cart, context=context)

    @classmethod
    @transaction.atomic
    def clear_cart(cls, cart: Cart) -> Cart:
        cart.items.all().delete()
        return cls._refresh_cart(cart)

    @classmethod
    def clear_current_cart(cls, user: User, context: dict | None = None) -> dict:
        cart = cls.get_current_cart(user)
        cart = cls.clear_cart(cart)
        return cls.serialize_cart(cart, context=context)
