import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.files import UUIDUploadTo
from apps.common.managers import ActiveManager


class Certificate(models.Model):
    """A certificate as a registry record in its own right.

    Split out of `CourseCompletion` because it outlives it: it can be issued by
    hand with no completion behind it, re-issued after a correction, and
    revoked, and a third party has to be able to verify it long afterwards.
    Deliberately has no delete endpoint, it records something asserted to an
    employer, so the registry must still answer for it years later.
    """

    class StatusChoices(models.TextChoices):
        VALID = "valid", "Valid"
        REVOKED = "revoked", "Revoked"

    class IssueReasonChoices(models.TextChoices):
        COMPLETION = "completion", "Completion"
        MANUAL = "manual", "Manual"
        REISSUE = "reissue", "Reissue"

    serial = models.CharField(max_length=32, unique=True)
    # The unguessable key, and the one printed on the PDF as the QR/verify link.
    # The serial is short enough to read out over the phone, which is exactly
    # what makes it too short to publish as the only lookup key.
    public_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    student_profile = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    # Nullable so the registry survives a hard-deleted course; display data comes
    # from the snapshots below, not from these FKs.
    course = models.ForeignKey(
        "courses.Course",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="certificates",
    )
    completion = models.ForeignKey(
        "enrollments.CourseCompletion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="certificates",
    )

    # Snapshots, frozen at issue time: the certificate asserts what was true then.
    student_name = models.CharField(max_length=255)
    course_title = models.CharField(max_length=255)
    final_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.VALID,
        db_index=True,
    )
    issue_reason = models.CharField(
        max_length=20,
        choices=IssueReasonChoices.choices,
        default=IssueReasonChoices.COMPLETION,
    )
    # Why a human overrode the automatic rule. Required by the manual and
    # re-issue endpoints, empty on the automatic completion path.
    issue_note = models.TextField(blank=True, default="")
    issued_at = models.DateTimeField(default=timezone.now)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_certificates",
    )

    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_certificates",
    )
    # Nullable rather than blank="": the public payload never carries it, and the
    # admin payload distinguishes "never revoked" from "revoked without a note".
    revoke_reason = models.TextField(null=True, blank=True)

    # A restore clears the three revoke fields, so `revoked_at` is non-null
    # exactly when the status is revoked, and records itself here instead.
    restored_at = models.DateTimeField(null=True, blank=True)
    restored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="restored_certificates",
    )
    restore_reason = models.TextField(null=True, blank=True)

    superseded_by = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supersedes",
    )

    # Lets a student or an administrator withdraw a certificate from public
    # verification without revoking it, which is a much harsher statement.
    is_public = models.BooleanField(default=True)

    # Set when the auto-revoke fired because the course completion was reverted.
    # The `completion` FK is SET_NULL, so once the row is gone nothing else
    # distinguishes "its completion was undone" from "it never had one".
    completion_reverted = models.BooleanField(default=False)

    # Populated only when this row rendered its own PDF (manual issue, re-issue).
    # Certificates issued for a completion read the file that completion stores.
    certificate_file = models.FileField(
        upload_to=UUIDUploadTo("certificates"),
        null=True,
        blank=True,
    )
    certificate_thumbnail = models.ImageField(
        upload_to=UUIDUploadTo("certificates/thumbnails"),
        null=True,
        blank=True,
    )

    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "certificates"
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["student_profile", "status"]),
            models.Index(fields=["course", "status"]),
            models.Index(fields=["issued_at"]),
        ]

    def __str__(self):
        return f"{self.serial} - {self.student_name} - {self.course_title}"

    @property
    def is_valid(self) -> bool:
        return self.status == self.StatusChoices.VALID

    @property
    def pdf_file(self):
        if self.certificate_file:
            return self.certificate_file
        return self.completion.certificate_file if self.completion_id else None

    @property
    def thumbnail_file(self):
        if self.certificate_thumbnail:
            return self.certificate_thumbnail
        return self.completion.certificate_thumbnail if self.completion_id else None
