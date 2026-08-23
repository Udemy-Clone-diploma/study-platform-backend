import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.exceptions import (
    AccountForbiddenError,
    AuthenticationError,
    EmailNotVerifiedError,
    GoogleAuthError,
    InvalidTokenError,
)
from apps.users.models import StudentProfile, User
from apps.users.services.email_service import EmailService
from apps.users.tokens import (
    email_verification_token,
    password_reset_token,
    teacher_invitation_token,
)


class AuthService:
    @staticmethod
    def _issue_jwt_pair(user: User) -> dict:
        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    @staticmethod
    def register(user: User) -> User:
        """Triggers post-registration side effects after the user has been created."""
        EmailService.send_verification_email(user)
        return user

    @classmethod
    def login(cls, email: str, password: str) -> dict:
        """Validates credentials and user state. Returns JWT token pair."""
        try:
            user = User.all_objects.get(email__iexact=email)
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

        return cls._issue_jwt_pair(user)

    @classmethod
    def google_login(cls, id_token_str: str) -> dict:
        """Verifies a Google ID token, finds-or-creates the user, and returns a JWT pair.

        Google already verifies the account's email ownership, so a verified Google
        email is trusted as a confirmed email on our side too.
        """
        try:
            payload = google_id_token.verify_oauth2_token(
                id_token_str, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID
            )
        except ValueError:
            raise GoogleAuthError("Invalid or expired Google ID token.")

        if not payload.get("email_verified"):
            raise GoogleAuthError("This Google account's email is not verified.")

        email = payload["email"]

        try:
            user = User.all_objects.get(email__iexact=email)
        except User.DoesNotExist:
            user = cls._create_user_from_google(payload)
        else:
            if user.is_deleted or user.is_blocked:
                raise AccountForbiddenError("This account has been deleted or blocked.")
            if user.status == User.StatusChoices.INACTIVE:
                raise AccountForbiddenError(
                    "This account is not active yet. Please finish the invitation "
                    "process from your email before signing in."
                )
            if not user.is_email_verified:
                user.is_email_verified = True
                user.save(update_fields=["is_email_verified"])

        return cls._issue_jwt_pair(user)

    @staticmethod
    def _create_user_from_google(payload: dict) -> User:
        """Creates a new student account from a verified Google ID token payload."""
        user = User(
            email=payload["email"],
            first_name=payload.get("given_name", ""),
            last_name=payload.get("family_name", ""),
            role=User.RoleChoices.STUDENT,
            is_email_verified=True,
        )
        user.set_unusable_password()
        user.save()
        StudentProfile.objects.create(user=user)

        picture_url = payload.get("picture")
        if picture_url:
            AuthService._save_avatar_from_url(user, picture_url)

        return user

    @staticmethod
    def _save_avatar_from_url(user: User, picture_url: str) -> None:
        """Best-effort import of the Google profile photo; silently skipped on failure."""
        try:
            response = requests.get(picture_url, timeout=5)
            response.raise_for_status()
        except requests.RequestException:
            return
        user.avatar.save(f"{user.pk}.jpg", ContentFile(response.content), save=True)

    @staticmethod
    def logout(refresh_token_str: str) -> None:
        """Blacklists the refresh token."""
        token = RefreshToken(refresh_token_str)
        token.blacklist()

    @staticmethod
    def refresh_access_token(refresh_token_str: str) -> dict:
        """Validates refresh token and user state. Returns refreshed token payload."""
        token = RefreshToken(refresh_token_str)
        user_id = token[jwt_settings.USER_ID_CLAIM]  # type: ignore
        user = User.all_objects.get(pk=user_id)

        if user.is_deleted:
            raise AccountForbiddenError("This account has been deleted.")

        if user.is_blocked:
            raise AccountForbiddenError("This account has been blocked.")

        access = token.access_token
        access["role"] = user.role
        payload = {"access": str(access)}

        if jwt_settings.ROTATE_REFRESH_TOKENS:
            if jwt_settings.BLACKLIST_AFTER_ROTATION:
                token.blacklist()

            refresh = RefreshToken.for_user(user)
            refresh["role"] = user.role
            payload["refresh"] = str(refresh)

        return payload

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
            user = User.all_objects.get(email__iexact=email, is_deleted=False, is_blocked=False)
        except User.DoesNotExist:
            return

        if not user.is_email_verified:
            EmailService.send_verification_email(user)

    @staticmethod
    def request_password_reset(email: str) -> None:
        """Sends a password reset email if the account exists, is active, and email verified."""
        try:
            user = User.all_objects.get(email__iexact=email, is_deleted=False, is_blocked=False)
            if user.is_email_verified:
                EmailService.send_password_reset_email(user)
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

    @staticmethod
    def _resolve_user_for_teacher_invitation(uidb64: str, token: str) -> User:
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.all_objects.get(pk=uid)
        except (ValueError, User.DoesNotExist):
            raise InvalidTokenError()

        if user.is_deleted or user.is_blocked:
            raise InvalidTokenError()

        if not teacher_invitation_token.check_token(user, token):
            raise InvalidTokenError()

        return user

    @classmethod
    def validate_teacher_invitation_token(cls, uidb64: str, token: str) -> None:
        """Validates a teacher invitation token without making any changes."""
        cls._resolve_user_for_teacher_invitation(uidb64, token)

    @staticmethod
    def resend_teacher_invitation_email(email: str) -> None:
        """Resends the invitation email if a pending, unactivated teacher account exists."""
        try:
            user = User.all_objects.get(
                email__iexact=email,
                role=User.RoleChoices.TEACHER,
                status=User.StatusChoices.INACTIVE,
                is_email_verified=False,
                is_deleted=False,
                is_blocked=False,
            )
        except User.DoesNotExist:
            return

        EmailService.send_teacher_invitation_email(user)

    @classmethod
    def confirm_teacher_invitation(cls, uidb64: str, token: str, password: str) -> None:
        """Sets the teacher's own password and activates the account.

        Since the link could only have reached the applicant's inbox, using
        it also counts as confirming the email, one step does both.
        """
        user = cls._resolve_user_for_teacher_invitation(uidb64, token)
        user.set_password(password)
        user.is_email_verified = True
        user.status = User.StatusChoices.ACTIVE
        user.save()
