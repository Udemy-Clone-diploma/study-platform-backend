from django.contrib import admin

from .models import Category, Course, Lesson, Module, Tag
from .signals import _recompute_lessons_count


class SoftDeleteAdminMixin:
    def get_queryset(self, request):
        return self.model.all_objects.all()

    def delete_model(self, request, obj):
        obj.is_deleted = True
        obj.save(update_fields=["is_deleted"])

    def delete_queryset(self, request, queryset):
        queryset.update(is_deleted=True)


class LessonsCountRecomputeMixin:
    """Bulk delete uses queryset.update(), which skips post_save/post_delete.

    Subclasses set ``affected_course_ids_path`` to the ORM path that resolves
    a row to its owning course id, and we call ``_recompute_lessons_count``
    once per distinct course after the bulk update.
    """

    affected_course_ids_path: str = ""

    def delete_queryset(self, request, queryset):
        course_ids = list(
            queryset.values_list(self.affected_course_ids_path, flat=True).distinct()
        )
        super().delete_queryset(request, queryset)  # type: ignore[misc]
        for course_id in course_ids:
            _recompute_lessons_count(course_id)


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
class CourseAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "slug", "status", "lessons_count", "is_deleted")
    list_filter = ("status", "is_deleted", "level", "language")
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ModuleInline]


@admin.register(Module)
class ModuleAdmin(LessonsCountRecomputeMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "course", "order", "is_deleted")
    list_filter = ("is_deleted", "course")
    list_select_related = ("course",)
    search_fields = ("title", "course__title")
    inlines = [LessonInline]
    affected_course_ids_path = "course_id"


@admin.register(Lesson)
class LessonAdmin(LessonsCountRecomputeMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "module", "course", "order", "duration_minutes", "is_deleted")
    list_filter = ("is_deleted", "module__course", "module")
    list_select_related = ("module__course",)
    search_fields = ("title", "module__title", "module__course__title")
    affected_course_ids_path = "module__course_id"

    @admin.display(description="Course", ordering="module__course__title")
    def course(self, obj):
        return obj.module.course
