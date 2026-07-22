from django.contrib import admin

from apps.certificates.models import Certificate
from apps.courses.admin import SoftDeleteAdminMixin


@admin.register(Certificate)
class CertificateAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("serial", "student_name", "course_title", "status", "issued_at")
    list_filter = ("status", "issue_reason", "is_public", "is_deleted")
    search_fields = ("serial", "student_name", "course_title", "public_uuid")
    readonly_fields = ("serial", "public_uuid", "created_at", "updated_at")
    raw_id_fields = (
        "student_profile",
        "course",
        "completion",
        "issued_by",
        "revoked_by",
        "restored_by",
        "superseded_by",
    )
