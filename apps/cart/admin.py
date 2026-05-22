from django.contrib import admin

from apps.cart.models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ("course", "added_at")
    readonly_fields = ("added_at",)
    autocomplete_fields = ("course",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("student_profile", "items_count", "total_price", "updated_at")
    list_select_related = ("student_profile__user",)
    search_fields = ("student_profile__user__email",)
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "course", "added_at")
    list_select_related = ("cart__student_profile__user", "course")
    search_fields = (
        "cart__student_profile__user__email",
        "course__title",
        "course__slug",
    )
