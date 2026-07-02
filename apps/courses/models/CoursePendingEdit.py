from django.db import models

from apps.users.models import ModeratorProfile


class CoursePendingEdit(models.Model):
    class StatusChoices(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending Moderation"
        NEEDS_REVISION = "needs_revision", "Needs Revision"

    course = models.OneToOneField(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="pending_edit",
    )

    # The hidden PENDING_EDIT shadow course the teacher actually edits. Its full
    # module/lesson/test/content-item tree IS the pending edit; on approval it's
    # merged onto `course` and then deleted (see PendingEditService.merge_into_live).
    draft_course = models.OneToOneField(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="as_draft_for",
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
    )

    moderator_profile = models.ForeignKey(
        ModeratorProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    moderator_comment = models.TextField(blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "course_pending_edits"

    def __str__(self):
        return f"PendingEdit({self.course.slug})[{self.status}]"
