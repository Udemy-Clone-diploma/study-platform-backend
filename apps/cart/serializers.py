from rest_framework import serializers

from apps.cart.models import Cart, CartItem
from apps.courses.models import Course
from apps.courses.serializers import CourseListSerializer


class CartItemSerializer(serializers.ModelSerializer):
    course = CourseListSerializer(read_only=True)
    course_id = serializers.IntegerField(read_only=True)
    unit_price = serializers.DecimalField(
        source="course.price",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id",
            "course_id",
            "course",
            "unit_price",
            "subtotal",
            "added_at",
        ]


class CartSerializer(serializers.ModelSerializer):
    student_profile_id = serializers.IntegerField(read_only=True)
    items = CartItemSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    total_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Cart
        fields = [
            "id",
            "student_profile_id",
            "items",
            "items_count",
            "total_price",
            "created_at",
            "updated_at",
        ]


class CartItemAddSerializer(serializers.Serializer):
    course_id = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.select_related("teacher_profile__user", "category")
        .prefetch_related("tags"),
        source="course",
        write_only=True,
    )


class CartItemRemoveSerializer(serializers.Serializer):
    course_id = serializers.IntegerField(min_value=1)
