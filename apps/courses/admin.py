from django.contrib import admin

from .models import Category, Course, Tag


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


admin.site.register(Course)
