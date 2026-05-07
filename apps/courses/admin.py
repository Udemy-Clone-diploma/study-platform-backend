from django.contrib import admin

from .models import Category, Course, Lesson, Module, Tag


class SoftDeleteAdminMixin:
    def get_queryset(self, request):
        return self.model.all_objects.all()

    def delete_model(self, request, obj):
        obj.is_deleted = True
        obj.save(update_fields=["is_deleted"])

    def delete_queryset(self, request, queryset):
        queryset.update(is_deleted=True)


class LessonInline(SoftDeleteAdminMixin, admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("title", "order", "duration_minutes", "is_deleted")
    show_change_link = True


class ModuleInline(SoftDeleteAdminMixin, admin.TabularInline):
    model = Module
    extra = 0
    fields = ("title", "order", "is_deleted")
    show_change_link = True


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


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status", "lessons_count", "is_deleted")
    list_filter = ("status", "is_deleted", "level", "language")
    search_fields = ("title", "slug")
    inlines = [ModuleInline]


@admin.register(Module)
class ModuleAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "course", "order", "is_deleted")
    list_filter = ("is_deleted", "course")
    list_select_related = ("course",)
    search_fields = ("title", "course__title")
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "module", "course", "order", "duration_minutes", "is_deleted")
    list_filter = ("is_deleted", "module__course", "module")
    list_select_related = ("module__course",)
    search_fields = ("title", "module__title", "module__course__title")

    @admin.display(description="Course", ordering="module__course__title")
    def course(self, obj):
        return obj.module.course
