from django.contrib.auth.tokens import (
    PasswordResetTokenGenerator as DjangoPasswordResetTokenGenerator,
)

from config import settings


class EmailVerificationTokenGenerator(DjangoPasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.is_email_verified}"

    @property
    def _timeout(self):
        return getattr(settings, "EMAIL_VERIFICATION_TIMEOUT", 60 * 60 * 24 * 2)


class PasswordResetTokenGenerator(DjangoPasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.password}"


class TeacherInvitationTokenGenerator(DjangoPasswordResetTokenGenerator):
    """Single-use link sent after a teacher application is approved.

    Completing it (setting a password) also confirms the email, so the hash
    bakes in both `password` and `is_email_verified` — either changing
    invalidates the link.
    """

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.password}{user.is_email_verified}"


email_verification_token = EmailVerificationTokenGenerator()
password_reset_token = PasswordResetTokenGenerator()
teacher_invitation_token = TeacherInvitationTokenGenerator()
