from django.conf import settings
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.users.tokens import email_verification_token, password_reset_token, teacher_invitation_token


class EmailService:
    @staticmethod
    def send_verification_email(user) -> None:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        url = f"{settings.FRONTEND_URL}/register/verify-email/{uid}/{token}/"

        send_mail(
            subject="Confirm your email address",
            message=f"The link is valid for 2 days:\n{url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )

    @staticmethod
    def send_password_reset_email(user) -> None:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = password_reset_token.make_token(user)
        url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

        send_mail(
            subject="Password reset",
            message=f"Follow the link to reset your password (valid for 1 hour):\n{url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )

    @staticmethod
    def send_teacher_invitation_email(user) -> None:
        """The one email sent after a teacher application is approved.

        A single link both confirms the email and lets the teacher set their
        own password — no generated password is ever emailed.
        """
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = teacher_invitation_token.make_token(user)
        url = f"{settings.FRONTEND_URL}/activate-teacher-account/{uid}/{token}/"

        send_mail(
            subject="Congratulations! Your teacher application has been approved",
            message=(
                "Your teacher registration application has been approved.\n"
                f"Follow the link to confirm your email and set your password:\n{url}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )

    @staticmethod
    def send_teacher_application_cancelled_email(application) -> None:
        comment_line = f"\n\nModerator comment:\n{application.moderator_comment}" if application.moderator_comment else ""
        send_mail(
            subject="Your teacher registration application has been cancelled",
            message=(
                "Unfortunately, your teacher registration application has been cancelled."
                f"{comment_line}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.email],
        )
