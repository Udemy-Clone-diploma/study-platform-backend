from django.contrib import admin

from apps.courses.admin import SoftDeleteAdminMixin
from apps.enrollments.models import Enrollment


@admin.register(Enrollment)
class EnrollmentAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "student_profile",
        "course",
        "order_id",
        "access_status",
        "access_granted_at",
        "access_until",
        "is_deleted",
    )
    list_filter = ("access_status", "is_deleted", "course")
    list_select_related = ("student_profile__user", "course")
    search_fields = ("student_profile__user__email", "course__title", "course__slug")
