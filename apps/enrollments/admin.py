from django.contrib import admin

from apps.enrollments.models import Enrollment


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "student_profile",
        "course",
        "order_id",
        "access_status",
        "access_granted_at",
        "access_until",
    )
    list_filter = ("access_status", "course")
    list_select_related = ("student_profile__user", "course")
    search_fields = ("student_profile__user__email", "course__title", "course__slug")
