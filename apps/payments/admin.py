from django.contrib import admin

from apps.payments.models import (
    Order,
    OrderItem,
    Payment,
    PaymentAttempt,
    PaymentInstallment,
    PaymentItem,
    Refund,
    TeacherPayoutAccount,
    WebhookEvent,
)

admin.site.register(TeacherPayoutAccount)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "course",
        "pricing_plan",
        "course_title",
        "course_slug",
        "pricing_plan_kind",
        "unit_amount",
        "currency",
        "created_at",
    )
    can_delete = False


class PaymentInstallmentInline(admin.TabularInline):
    model = PaymentInstallment
    extra = 0
    readonly_fields = (
        "installment_number",
        "amount",
        "currency",
        "due_date",
        "status",
        "paid_at",
        "created_at",
        "updated_at",
    )
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "total_amount",
        "currency",
        "status",
        "payment_type",
        "installments_count",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "payment_type", "currency")
    list_select_related = ("user", "student_profile__user")
    search_fields = ("user__email",)
    readonly_fields = ("created_at", "updated_at", "completed_at")
    inlines = [OrderItemInline, PaymentInstallmentInline]


class PaymentItemInline(admin.TabularInline):
    model = PaymentItem
    extra = 0
    readonly_fields = (
        "course",
        "pricing_plan",
        "course_title",
        "course_slug",
        "pricing_plan_kind",
        "unit_amount",
        "currency",
        "created_at",
    )
    can_delete = False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "order",
        "installment",
        "amount",
        "currency",
        "status",
        "payment_method",
        "created_at",
        "processed_at",
    )
    list_filter = ("status", "payment_method", "currency")
    list_select_related = ("user", "student_profile__user")
    search_fields = (
        "user__email",
        "order__id",
        "stripe_session_id",
        "stripe_payment_intent_id",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "processed_at",
        "checkout_url",
        "stripe_payment_intent_id",
        "stripe_session_id",
        "stripe_customer_id",
    )
    inlines = [PaymentItemInline]


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "payment", "status", "stripe_charge_id", "created_at")
    list_filter = ("status",)
    list_select_related = ("payment",)
    search_fields = ("payment__user__email", "stripe_charge_id")


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("id", "payment", "amount", "status", "created_at", "processed_at")
    list_filter = ("status",)
    list_select_related = ("payment", "created_by")
    search_fields = ("payment__user__email", "stripe_refund_id")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_id", "event_type", "status", "created_at")
    list_filter = ("provider", "event_type", "status")
    search_fields = ("event_id", "event_type")
    readonly_fields = ("created_at", "processed_at")
