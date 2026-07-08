from django.contrib import admin

from .models import Review, ReviewReport


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("course", "student", "rating", "moderation_status", "is_deleted", "created_at")
    list_filter = ("rating", "moderation_status", "is_deleted")
    search_fields = ("course__title", "student__email", "text")
    list_select_related = ("course", "student", "moderator_profile")
    raw_id_fields = ("course", "student", "moderator_profile")

    def get_queryset(self, request):
        return self.model.all_objects.all()

    def delete_model(self, request, obj):
        obj.is_deleted = True
        obj.save(update_fields=["is_deleted"])

    def delete_queryset(self, request, queryset):
        queryset.update(is_deleted=True)


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ("review", "reporter", "created_at")
    search_fields = ("review__course__title", "reporter__email", "reason")
    list_select_related = ("review", "reporter")
    raw_id_fields = ("review", "reporter")
