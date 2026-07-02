from django.core.validators import FileExtensionValidator
from django.db import models

from apps.common.files import UUIDUploadTo
from apps.courses.models.Course import COURSE_IMAGE_EXTENSIONS
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

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
    )

    # Course metadata snapshot (full intended state)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    short_description = models.CharField(max_length=500)
    full_description = models.TextField()
    image = models.FileField(
        upload_to=UUIDUploadTo("courses/pending"),
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=COURSE_IMAGE_EXTENSIONS)],
    )
    level = models.CharField(max_length=20)
    language = models.CharField(max_length=20)
    mode = models.CharField(max_length=20)
    delivery_type = models.CharField(max_length=20)
    course_type = models.CharField(max_length=30)
    duration_hours = models.PositiveIntegerField(null=True, blank=True, default=0)
    with_certificate = models.BooleanField(default=False)
    is_on_sale = models.BooleanField(default=False)
    category = models.ForeignKey(
        "courses.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    tag_ids = models.JSONField(default=list)

    # Full modules / lessons / tests / questions snapshot
    modules_snapshot = models.JSONField(default=list)

    # Moderation
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