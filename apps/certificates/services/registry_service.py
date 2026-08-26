import logging

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.certificates.exceptions import (
    CertificateAlreadyExistsError,
    CertificateAlreadyRevokedError,
    CertificateNotFoundError,
    CertificateRenderError,
    CertificateSupersededError,
    CompletionRevertedError,
    StudentNotEnrolledError,
)
from apps.certificates.models import Certificate
from apps.certificates.serials import generate_unique_serial

logger = logging.getLogger(__name__)


class CertificateRegistryService:
    """Issues, re-issues, revokes and verifies registry rows.

    The PDF itself is rendered by `apps.enrollments.services.certificate_service
    .CertificateService`, which owns the artwork; this service owns the record.
    """

    @classmethod
    def issue_for_completion(cls, completion, course, user) -> Certificate:
        """The automatic path, called when a course completion generates a
        certificate. Reads the PDF the completion already stores rather than
        rendering a second copy."""
        return Certificate.objects.create(
            serial=generate_unique_serial(timezone.now().year),
            student_profile=completion.student_profile,
            course=course,
            completion=completion,
            student_name=user.get_full_name(),
            course_title=completion.title,
            final_score=completion.final_score,
            issue_reason=Certificate.IssueReasonChoices.COMPLETION,
            issued_at=completion.completed_at or timezone.now(),
        )

    @classmethod
    @transaction.atomic
    def issue_manually(cls, *, student_user, course, reason: str, issued_by) -> Certificate:
        """The override path: a student who did not reach `passing_score`, or
        who did the work offline."""
        from apps.enrollments.services import EnrollmentService

        student_profile = cls._student_profile(student_user)
        student_name = student_user.get_full_name()

        if not EnrollmentService.is_enrolled(student_user, course):
            raise StudentNotEnrolledError(f"{student_name} is not enrolled in {course.title}.")
        cls._assert_no_valid_certificate(student_profile, course, student_name)

        certificate = Certificate.objects.create(
            serial=generate_unique_serial(timezone.now().year),
            student_profile=student_profile,
            course=course,
            student_name=student_name,
            course_title=course.title,
            issue_reason=Certificate.IssueReasonChoices.MANUAL,
            issue_note=reason,
            issued_by=issued_by,
        )
        cls._render_and_attach(certificate, course)
        return certificate

    @classmethod
    @transaction.atomic
    def reissue(cls, *, certificate: Certificate, reason: str, issued_by) -> Certificate:
        """Replace a certificate after a correction (a misspelled name, a
        renamed course). The old row stays in the registry pointing at the new
        one, so an employer holding the old PDF still resolves."""
        if certificate.superseded_by_id:
            raise CertificateSupersededError(
                f"{certificate.serial} has already been replaced by "
                f"{certificate.superseded_by.serial}."
            )

        course = certificate.course
        if course is None:
            raise CertificateSupersededError(
                f"{certificate.serial} cannot be re-issued: its course no longer "
                f"exists, so there is nothing to render a new certificate from."
            )

        student_user = certificate.student_profile.user
        replacement = Certificate.objects.create(
            serial=generate_unique_serial(timezone.now().year),
            student_profile=certificate.student_profile,
            course=course,
            completion=certificate.completion,
            # Re-read from live data: correcting it is the whole point.
            student_name=student_user.get_full_name(),
            course_title=course.title if course else certificate.course_title,
            final_score=certificate.final_score,
            issue_reason=Certificate.IssueReasonChoices.REISSUE,
            issue_note=reason,
            issued_by=issued_by,
            is_public=certificate.is_public,
        )
        cls._render_and_attach(replacement, course)

        certificate.superseded_by = replacement
        certificate.save(update_fields=["superseded_by", "updated_at"])
        return replacement

    @classmethod
    def revoke(cls, *, certificate: Certificate, reason: str, revoked_by) -> Certificate:
        if certificate.status == Certificate.StatusChoices.REVOKED:
            raise CertificateAlreadyRevokedError(
                f"{certificate.serial} was already revoked on "
                f"{timezone.localtime(certificate.revoked_at):%d %b %Y}."
            )

        certificate.status = Certificate.StatusChoices.REVOKED
        certificate.revoked_at = timezone.now()
        certificate.revoked_by = revoked_by
        certificate.revoke_reason = reason
        certificate.save(
            update_fields=[
                "status",
                "revoked_at",
                "revoked_by",
                "revoke_reason",
                "updated_at",
            ]
        )
        return certificate

    @classmethod
    def restore(cls, *, certificate: Certificate, reason: str, restored_by) -> Certificate:
        """Undo a revoke. Clears the revoke fields so `revoked_at` stays
        non-null exactly when the status is revoked, and records the undo in
        the restore fields instead."""
        if certificate.status == Certificate.StatusChoices.VALID:
            raise CertificateAlreadyRevokedError(f"{certificate.serial} is not revoked.")
        if certificate.completion_reverted:
            raise CompletionRevertedError(
                f"{certificate.serial} cannot be restored: the course completion "
                f"behind it was reverted by the instructor. Have the student "
                f"complete the course again, or issue a new certificate by hand."
            )

        certificate.status = Certificate.StatusChoices.VALID
        certificate.revoked_at = None
        certificate.revoked_by = None
        certificate.revoke_reason = None
        certificate.restored_at = timezone.now()
        certificate.restored_by = restored_by
        certificate.restore_reason = reason
        certificate.save(
            update_fields=[
                "status",
                "revoked_at",
                "revoked_by",
                "revoke_reason",
                "restored_at",
                "restored_by",
                "restore_reason",
                "updated_at",
            ]
        )
        return certificate

    @staticmethod
    def verify(lookup: str) -> Certificate:
        """Resolve a serial or a public_uuid for the public verify page.

        A revoked certificate resolves: "this exists but no longer stands" is
        different information from "this never existed".
        """
        certificate = (
            Certificate.objects.select_related("superseded_by")
            .filter(is_public=True)
            .filter(serial__iexact=lookup)
            .first()
        )
        if certificate is None and _looks_like_uuid(lookup):
            certificate = (
                Certificate.objects.select_related("superseded_by")
                .filter(is_public=True, public_uuid=lookup)
                .first()
            )
        if certificate is None:
            raise CertificateNotFoundError("No certificate found with this serial.")
        return certificate

    @classmethod
    def revoke_for_deleted_completion(cls, completion) -> None:
        """A teacher reverting a completion takes the certificate with it: the
        completion row and its PDF are deleted, so leaving a `valid` registry
        entry behind would assert something the platform no longer stands by."""
        for certificate in Certificate.objects.filter(
            completion=completion, status=Certificate.StatusChoices.VALID
        ):
            cls.revoke(
                certificate=certificate,
                reason="Course completion was reverted by the instructor.",
                revoked_by=None,
            )
            # Blocks /restore/, which would otherwise re-assert the certificate
            # while the completion behind it is still undone.
            certificate.completion_reverted = True
            certificate.save(update_fields=["completion_reverted", "updated_at"])

    @staticmethod
    def set_visibility(*, certificate: Certificate, is_public: bool) -> Certificate:
        """Withdraw a certificate from (or return it to) public verification.
        Distinct from revoking: the certificate still stands, it is just not
        answerable to strangers."""
        certificate.is_public = is_public
        certificate.save(update_fields=["is_public", "updated_at"])
        return certificate

    @staticmethod
    def _student_profile(student_user):
        from apps.users.models import StudentProfile

        try:
            return student_user.student_profile
        except StudentProfile.DoesNotExist as exc:
            raise StudentNotEnrolledError(
                f"{student_user.get_full_name()} has no student profile."
            ) from exc

    @staticmethod
    def _assert_no_valid_certificate(student_profile, course, student_name: str) -> None:
        exists = Certificate.objects.filter(
            student_profile=student_profile,
            course=course,
            status=Certificate.StatusChoices.VALID,
            superseded_by__isnull=True,
        ).exists()
        if exists:
            raise CertificateAlreadyExistsError(
                f"{student_name} already holds a valid certificate for {course.title}."
            )

    @staticmethod
    def _render_and_attach(certificate: Certificate, course) -> None:
        from apps.enrollments.services.certificate_service import CertificateService

        try:
            teacher_profile = getattr(course, "teacher_profile", None)
            pdf_bytes, thumbnail_bytes = CertificateService.render_certificate_assets(
                course=course,
                student_name=certificate.student_name,
                course_title=certificate.course_title,
                teacher_name=(teacher_profile.user.get_full_name() if teacher_profile else ""),
                completed_at=certificate.issued_at,
            )
        except Exception as exc:
            # Raised, not swallowed: both callers run in a transaction, so the
            # row rolls back rather than persisting with a null certificate_url
            # that the caller was promised would be populated.
            logger.exception("Certificate rendering failed for certificate %s", certificate.id)
            raise CertificateRenderError(
                f"Could not generate the certificate PDF for {course.title}. "
                f"Check the course's certificate settings and try again."
            ) from exc

        certificate.certificate_file.save(
            f"certificate-{certificate.serial}.pdf",
            ContentFile(pdf_bytes),
            save=False,
        )
        certificate.certificate_thumbnail.save(
            f"certificate-{certificate.serial}.jpg",
            ContentFile(thumbnail_bytes),
            save=False,
        )
        certificate.save(update_fields=["certificate_file", "certificate_thumbnail", "updated_at"])


def _looks_like_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
