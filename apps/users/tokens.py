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


email_verification_token = EmailVerificationTokenGenerator()
password_reset_token = PasswordResetTokenGenerator()
