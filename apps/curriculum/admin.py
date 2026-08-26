from django.contrib import admin

from apps.courses.admin import SoftDeleteAdminMixin

from .models import Lesson, Module, Question, Test
from .signals import _recompute_lessons_count


class LessonsCountRecomputeMixin:
    """Bulk delete uses queryset.update(), which skips post_save/post_delete.

    Subclasses set ``affected_course_ids_path`` to the ORM path that resolves
    a row to its owning course id, and we call ``_recompute_lessons_count``
    once per distinct course after the bulk update.
    """

    affected_course_ids_path: str = ""

    def delete_queryset(self, request, queryset):
        course_ids = list(queryset.values_list(self.affected_course_ids_path, flat=True).distinct())
        super().delete_queryset(request, queryset)  # type: ignore[misc]
        for course_id in course_ids:
            _recompute_lessons_count(course_id)


class LessonInline(SoftDeleteAdminMixin, admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("title", "order", "duration_minutes", "is_preview", "is_deleted")
    show_change_link = True


class TestInline(SoftDeleteAdminMixin, admin.TabularInline):
    model = Test
    extra = 0
    fields = (
        "title",
        "passing_score",
        "duration_minutes",
        "allow_retakes",
        "max_attempts",
        "order",
        "is_deleted",
    )
    show_change_link = True


class QuestionInline(SoftDeleteAdminMixin, admin.TabularInline):
    model = Question
    extra = 0
    fields = (
        "question_type",
        "text",
        "options",
        "correct_indices",
        "correct_bool",
        "sample_answer",
        "accepted_answers",
        "order",
        "is_deleted",
    )
    show_change_link = True


class ModuleInline(SoftDeleteAdminMixin, admin.TabularInline):
    model = Module
    extra = 0
    fields = ("title", "order", "is_deleted")
    show_change_link = True


@admin.register(Module)
class ModuleAdmin(LessonsCountRecomputeMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "course", "order", "is_deleted")
    list_filter = ("is_deleted", "course")
    list_select_related = ("course",)
    search_fields = ("title", "course__title")
    inlines = [LessonInline, TestInline]
    affected_course_ids_path = "course_id"


@admin.register(Lesson)
class LessonAdmin(LessonsCountRecomputeMixin, SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "title",
        "module",
        "course",
        "order",
        "duration_minutes",
        "is_preview",
        "is_deleted",
    )
    list_filter = ("is_deleted", "is_preview", "module__course", "module")
    list_select_related = ("module__course",)
    search_fields = ("title", "module__title", "module__course__title")
    affected_course_ids_path = "module__course_id"

    @admin.display(description="Course", ordering="module__course__title")
    def course(self, obj):
        return obj.module.course


@admin.register(Test)
class TestAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("title", "module", "course", "passing_score", "order", "is_deleted")
    list_filter = ("is_deleted", "module__course")
    list_select_related = ("module__course",)
    search_fields = ("title", "module__title", "module__course__title")
    inlines = [QuestionInline]

    @admin.display(description="Course", ordering="module__course__title")
    def course(self, obj):
        return obj.module.course


@admin.register(Question)
class QuestionAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("text_short", "question_type", "test", "order", "is_deleted")
    list_filter = ("is_deleted", "question_type")
    search_fields = ("text", "test__title")

    @admin.display(description="Question")
    def text_short(self, obj):
        return obj.text[:60] + "…" if len(obj.text) > 60 else obj.text
