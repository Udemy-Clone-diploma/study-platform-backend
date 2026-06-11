from django.db import models

from apps.users.models import ModeratorProfile, TeacherProfile


class RejectedCourseRecord(models.Model):
    """Immutable snapshot created when a moderator rejects a course"""

    course = models.ForeignKey(
        "Course",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rejection_records",
    )
    teacher_profile = models.ForeignKey(
        TeacherProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="course_rejection_records",
    )
    moderator_profile = models.ForeignKey(
        ModeratorProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="course_rejection_records",
    )

    # Course snapshot — frozen at rejection time
    course_slug = models.CharField(max_length=255)
    course_title = models.CharField(max_length=255)
    course_image_url = models.TextField(null=True, blank=True)
    course_category = models.CharField(max_length=255, blank=True, default="")
    course_level = models.CharField(max_length=20, blank=True, default="")

    # For pending-edit rejections: which fields the teacher changed
    changed_fields = models.JSONField(default=list, blank=True)

    # Moderation review snapshot
    basics_field_statuses = models.JSONField(default=dict, blank=True)
    basics_action = models.CharField(max_length=20, blank=True, default="")
    basics_comment = models.TextField(blank=True, default="")
    content_item_statuses = models.JSONField(default=dict, blank=True)
    content_action = models.CharField(max_length=20, blank=True, default="")
    content_comment = models.TextField(blank=True, default="")
    final_action = models.CharField(max_length=20, blank=True, default="")
    final_comment = models.TextField(blank=True, default="")

    rejected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "course_rejection_records"
        ordering = ["-rejected_at"]

    def __str__(self):
        return f"Rejection of {self.course_title!r} at {self.rejected_at:%Y-%m-%d}"
