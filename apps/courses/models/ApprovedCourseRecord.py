from django.db import models

from apps.users.models import ModeratorProfile, TeacherProfile


class ApprovedCourseRecord(models.Model):
    """Immutable snapshot created when a moderator approves a course. As history"""

    course = models.ForeignKey(
        "Course",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approval_records",
    )
    teacher_profile = models.ForeignKey(
        TeacherProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="course_approval_records",
    )
    moderator_profile = models.ForeignKey(
        ModeratorProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="course_approval_records",
    )

    # Course snapshot, frozen at approval time
    course_slug = models.CharField(max_length=255)
    course_title = models.CharField(max_length=255)
    course_image_url = models.TextField(null=True, blank=True)
    course_category = models.CharField(max_length=255, blank=True, default="")
    course_level = models.CharField(max_length=20, blank=True, default="")

    # For pending-edit approvals: which fields the teacher changed
    changed_fields = models.JSONField(default=list, blank=True)

    approved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "course_approval_records"
        ordering = ["-approved_at"]

    def __str__(self):
        return f"Approval of {self.course_title!r} at {self.approved_at:%Y-%m-%d}"
