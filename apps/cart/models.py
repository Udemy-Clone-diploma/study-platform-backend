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

    @property
    def currency(self) -> str | None:
        currencies = {item.currency for item in self.items.all() if item.currency}
        if len(currencies) == 1:
            return currencies.pop()
        return None

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
    pricing_plan = models.ForeignKey(
        "courses.PricingPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
    def selected_pricing_plan(self):
        if self.pricing_plan_id:
            return self.pricing_plan
        return self.course.pricing_plans.order_by("price", "id").first()

    @property
    def unit_price(self) -> Decimal:
        plan = self.selected_pricing_plan
        return plan.price if plan else Decimal("0.00")

    @property
    def currency(self) -> str | None:
        plan = self.selected_pricing_plan
        return plan.currency if plan else None

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price

    def __str__(self):
        return f"{self.cart.student_profile.user.email} -> {self.course.title}"
