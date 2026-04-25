from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.settings import api_settings as jwt_settings

from apps.users.models import User
from apps.users.services.send_email_service import (
    password_reset_token,
    send_password_reset_email,
    send_verification_email,
)
from apps.users.services.token_generator_service import email_verification_token
from apps.users.services.tokens import get_tokens_for_user


class AuthenticationError(Exception):
    pass


class EmailNotVerifiedError(Exception):
    pass


class AccountForbiddenError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


class AuthService:
    @staticmethod
    def login(email: str, password: str) -> dict:
        """Validates credentials and user state. Returns JWT token pair."""
        try:
            user = User.all_objects.get(email=email)
        except User.DoesNotExist:
            raise AuthenticationError("Invalid email or password.")

        if not user.check_password(password):
            raise AuthenticationError("Invalid email or password.")

        if not user.is_email_verified:
            raise EmailNotVerifiedError("Please confirm your email before logging in")

        if user.is_deleted:
            raise AccountForbiddenError("This account has been deleted.")

        if user.is_blocked:
            raise AccountForbiddenError("This account has been blocked.")

        return get_tokens_for_user(user)

    @staticmethod
    def logout(refresh_token_str: str) -> None:
        """Blacklists the refresh token."""
        token = RefreshToken(refresh_token_str)
        token.blacklist()

    @staticmethod
    def refresh_access_token(refresh_token_str: str) -> str:
        """Validates refresh token and user state. Returns new access token string."""
        token = RefreshToken(refresh_token_str)
        user_id = token[jwt_settings.USER_ID_CLAIM]  # type: ignore
        user = User.all_objects.get(pk=user_id)

        if user.is_deleted:
            raise AccountForbiddenError("This account has been deleted.")

        if user.is_blocked:
            raise AccountForbiddenError("This account has been blocked.")

        access = token.access_token
        access["role"] = user.role
        return str(access)

    @staticmethod
    def verify_email(uidb64: str, token: str) -> None:
        """Verifies email confirmation token and marks the user as verified."""
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.all_objects.get(pk=uid)
        except (ValueError, User.DoesNotExist):
            raise InvalidTokenError()

        if user.is_deleted or user.is_blocked:
            raise InvalidTokenError()

        if not email_verification_token.check_token(user, token):
            raise InvalidTokenError()

        user.is_email_verified = True
        user.save()

    @staticmethod
    def resend_verification_email(email: str) -> None:
        """Sends a verification email if the account exists, is active, and unverified."""
        try:
            user = User.all_objects.get(email=email, is_deleted=False, is_blocked=False)
        except User.DoesNotExist:
            return

        if not user.is_email_verified:
            send_verification_email(user)

    @staticmethod
    def request_password_reset(email: str) -> None:
        """Sends a password reset email if the account exists, is active, and email verified."""
        try:
            user = User.all_objects.get(email=email, is_deleted=False, is_blocked=False)
            if user.is_email_verified:
                send_password_reset_email(user)
        except User.DoesNotExist:
            pass

    @staticmethod
    def _resolve_user_for_password_reset(uidb64: str, token: str) -> User:
        """Decodes uidb64 and validates password reset token. Returns user."""
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.all_objects.get(pk=uid)
        except (ValueError, User.DoesNotExist):
            raise InvalidTokenError()

        if user.is_deleted or user.is_blocked:
            raise InvalidTokenError()

        if not password_reset_token.check_token(user, token):
            raise InvalidTokenError()

        return user

    @classmethod
    def validate_password_reset_token(cls, uidb64: str, token: str) -> None:
        """Validates password reset token without making any changes."""
        cls._resolve_user_for_password_reset(uidb64, token)

    @classmethod
    def confirm_password_reset(cls, uidb64: str, token: str, password: str) -> None:
        """Validates token and sets the new password."""
        user = cls._resolve_user_for_password_reset(uidb64, token)
        user.set_password(password)
        user.save()
