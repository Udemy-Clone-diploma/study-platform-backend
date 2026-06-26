from django.conf import settings
from django.db import models

from apps.common.files import UUIDUploadTo


class HomeworkAssignment(models.Model):
    class StatusChoices(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        CLOSED = "closed", "Closed"

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="homework_assignments",
    )
    module = models.ForeignKey(
        "curriculum.Module",
        on_delete=models.SET_NULL,
        related_name="homework_assignments",
        null=True,
        blank=True,
    )
    lesson = models.ForeignKey(
        "curriculum.Lesson",
        on_delete=models.SET_NULL,
        related_name="homework_assignments",
        null=True,
        blank=True,
    )
    test = models.ForeignKey(
        "curriculum.Test",
        on_delete=models.SET_NULL,
        related_name="homework_assignments",
        null=True,
        blank=True,
    )
    source_assignment = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="reused_assignments",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_homework_assignments",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    due_at = models.DateTimeField(null=True, blank=True)
    max_score = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "homework_assignments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.course.title}: {self.title}"


class HomeworkAssignmentRecipient(models.Model):
    """A concrete student enrollment selected to receive an assignment."""

    assignment = models.ForeignKey(
        HomeworkAssignment,
        on_delete=models.CASCADE,
        related_name="recipients",
    )
    enrollment = models.ForeignKey(
        "enrollments.Enrollment",
        on_delete=models.CASCADE,
        related_name="homework_recipients",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "homework_assignment_recipients"
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "enrollment"],
                name="unique_homework_assignment_recipient",
            )
        ]


class HomeworkSubmission(models.Model):
    class StatusChoices(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWED = "reviewed", "Reviewed"

    assignment = models.ForeignKey(
        HomeworkAssignment,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    enrollment = models.ForeignKey(
        "enrollments.Enrollment",
        on_delete=models.CASCADE,
        related_name="homework_submissions",
    )
    content = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.SUBMITTED,
    )
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True, default="")
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "homework_submissions"
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "enrollment"],
                name="unique_homework_submission_per_enrollment",
            )
        ]


class HomeworkAssignmentAttachment(models.Model):
    assignment = models.ForeignKey(
        HomeworkAssignment,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to=UUIDUploadTo("homework/assignments"))
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_homework_assignment_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "homework_assignment_attachments"
        ordering = ["created_at"]


class HomeworkSubmissionAttachment(models.Model):
    submission = models.ForeignKey(
        HomeworkSubmission,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to=UUIDUploadTo("homework/submissions"))
    original_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "homework_submission_attachments"
        ordering = ["created_at"]
