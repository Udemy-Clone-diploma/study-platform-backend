from django.contrib import admin

from .models import Category, Cohort, Course, PricingPlan, Tag


class SoftDeleteAdminMixin:
    def get_queryset(self, request):
        return self.model.all_objects.all()

    def delete_model(self, request, obj):
        obj.is_deleted = True
        obj.save(update_fields=["is_deleted"])

    def delete_queryset(self, request, queryset):
        queryset.update(is_deleted=True)


@admin.register(Tag)
class TagAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("name", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class PricingPlanInline(admin.TabularInline):
    model = PricingPlan
    extra = 0
    fields = ("kind", "price", "currency", "installment_count", "installment_amount")


class CohortInline(admin.TabularInline):
    model = Cohort
    extra = 0
    fields = (
        "delivery_mode",
        "duration_months",
        "hours_per_week_min",
        "hours_per_week_max",
        "group_size",
        "start_date",
    )


@admin.register(Course)
class CourseAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "slug", "status", "lessons_count", "is_deleted")
    list_filter = ("status", "is_deleted", "level", "language")
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [PricingPlanInline, CohortInline]


@admin.register(PricingPlan)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = ("course", "kind", "price", "currency", "installment_count")
    list_filter = ("kind", "currency")
    search_fields = ("course__title", "course__slug")
    list_select_related = ("course",)
    raw_id_fields = ("course",)


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = (
        "course", "delivery_mode", "duration_months", "start_date", "group_size",
    )
    list_filter = ("delivery_mode",)
    search_fields = ("course__title", "course__slug")
    list_select_related = ("course",)
    raw_id_fields = ("course",)
