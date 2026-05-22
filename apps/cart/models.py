from decimal import Decimal

from django.db import models


class Cart(models.Model):
    student_profile = models.OneToOneField(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="cart",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "carts"
        ordering = ["-updated_at"]

    @property
    def items_count(self) -> int:
        return self.items.count()

    @property
    def total_price(self) -> Decimal:
        return sum((item.subtotal for item in self.items.all()), Decimal("0.00"))

    def __str__(self):
        return f"Cart: {self.student_profile.user.email}"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cart_items"
        ordering = ["-added_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "course"],
                name="unique_cart_item_per_course",
            ),
        ]

    @property
    def subtotal(self) -> Decimal:
        return self.course.price

    def __str__(self):
        return f"{self.cart.student_profile.user.email} -> {self.course.title}"
