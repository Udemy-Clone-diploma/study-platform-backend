from django.contrib import admin

from apps.courses.admin import SoftDeleteAdminMixin
from apps.enrollments.models import Enrollment, LessonCompletion


@admin.register(Enrollment)
class EnrollmentAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "student_profile",
        "course",
        "delivery_format",
        "order_id",
        "access_status",
        "access_granted_at",
        "access_until",
        "lessons_completed_count",
        "is_deleted",
    )
    list_filter = ("access_status", "is_deleted", "course")
    list_select_related = ("student_profile__user", "course", "delivery_format")
    search_fields = ("student_profile__user__email", "course__title", "course__slug")


@admin.register(LessonCompletion)
class LessonCompletionAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "lesson", "completed_at")
    list_filter = ("lesson__module__course",)
    list_select_related = (
        "enrollment__student_profile__user",
        "enrollment__course",
        "lesson__module__course",
    )
    search_fields = (
        "enrollment__student_profile__user__email",
        "enrollment__course__title",
        "lesson__title",
    )
