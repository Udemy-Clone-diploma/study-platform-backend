from django.contrib import admin, messages

from .models import Category, Cohort, Course, CoursePendingEdit, PricingPlan, Tag


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


@admin.register(CoursePendingEdit)
class CoursePendingEditAdmin(admin.ModelAdmin):
    list_display = ("course", "status", "submitted_at", "moderator_profile", "short_comment")
    list_filter = ("status",)
    search_fields = ("course__title", "course__slug")
    readonly_fields = (
        "course", "status", "submitted_at", "created_at", "updated_at",
        "title", "subtitle", "short_description", "full_description",
        "level", "language", "mode", "delivery_type", "course_type",
        "duration_hours", "with_certificate", "is_on_sale", "category",
        "tag_ids", "modules_snapshot",
    )
    fields = readonly_fields + ("moderator_profile", "moderator_comment")
    actions = ["approve_changes", "reject_changes"]

    @admin.display(description="Comment")
    def short_comment(self, obj):
        return (obj.moderator_comment[:60] + "…") if len(obj.moderator_comment) > 60 else obj.moderator_comment

    @admin.action(description="Approve selected pending edits (apply to live course)")
    def approve_changes(self, request, queryset):
        from apps.courses.services.pending_edit_service import PendingEditService
        approved = 0
        for pe in queryset:
            try:
                PendingEditService.approve(pe)
                approved += 1
            except Exception as exc:
                self.message_user(request, f"Error approving {pe.course}: {exc}", messages.ERROR)
        if approved:
            self.message_user(request, f"{approved} pending edit(s) approved and applied.", messages.SUCCESS)

    @admin.action(description="Reject selected pending edits (return for revision)")
    def reject_changes(self, request, queryset):
        from apps.courses.services.pending_edit_service import PendingEditService
        count = queryset.count()
        for pe in queryset:
            PendingEditService.reject(pe, comment="Returned for revision by moderator.")
        self.message_user(request, f"{count} pending edit(s) returned for revision.", messages.WARNING)


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = (
        "course", "delivery_mode", "duration_months", "start_date", "group_size",
    )
    list_filter = ("delivery_mode",)
    search_fields = ("course__title", "course__slug")
    list_select_related = ("course",)
    raw_id_fields = ("course",)
