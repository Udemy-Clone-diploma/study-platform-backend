from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.users.services.email_messages_service import EmailMessages
from apps.users.models import User
from apps.users.services.token_generator_service import email_verification_token, password_reset_token

from django.core.mail import send_mail
from django.conf import settings
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str


class EmailService:
    @staticmethod
    def get_user_by_uid(uidb64: str) -> User:
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            return User.all_objects.get(pk=uid)
        except (ValueError, User.DoesNotExist):
            raise ValidationError({"detail": EmailMessages.INVALID_LINK})

    @staticmethod
    def send_verification_email(user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        url = f"{settings.FRONTEND_URL}/register/verify-email/{uid}/{token}/"

        send_mail(
            subject="Підтвердіть вашу електронну пошту",
            message=f"Посилання дійсне 2 дні:\n{url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )

    @staticmethod
    def send_password_reset_email(user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = password_reset_token.make_token(user)
        url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
 
        send_mail(
            subject="Скидання пароля",
            message=f"Перейдіть за посиланням, щоб скинути пароль (діє 1 годину):\n{url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
 


    @staticmethod
    @transaction.atomic
    def verify_email(uidb64: str, token: str) -> User:
        user = EmailService.get_user_by_uid(uidb64)

        if user.is_deleted or user.is_blocked:
            raise ValidationError({"detail": EmailMessages.INVALID_LINK})

        if not email_verification_token.check_token(user, token):
            raise ValidationError({"detail": EmailMessages.INVALID_LINK})

        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
        return user
    
    @staticmethod
    def resend_verification_email(email: str) -> None:
        if not email:
            raise ValidationError({"detail": EmailMessages.EMAIL_REQUIRED})

        try:
            user = User.all_objects.get(
                email=email,
                is_deleted=False,
                is_blocked=False,
            )
        except User.DoesNotExist:
            return

        if not user.is_email_verified:
            EmailService.send_verification_email(user)

    @staticmethod
    def request_password_reset(email: str) -> None:
        if not email:
            raise ValidationError({"detail": EmailMessages.EMAIL_REQUIRED})

        try:
            user = User.all_objects.get(
                email=email,
                is_deleted=False,
                is_blocked=False,
            )
            if user.is_email_verified:
                EmailService.send_password_reset_email(user)
        except User.DoesNotExist:
            pass

    @staticmethod
    @transaction.atomic
    def confirm_password_reset(uidb64: str, token: str, password: str) -> User:
        if not password or len(password) < 8:
            raise ValidationError({"detail": "Password must be at least 8 characters."})

        user = EmailService.get_user_by_uid(uidb64)

        if user.is_deleted or user.is_blocked:
            raise ValidationError({"detail": EmailMessages.PASSWORD_RESET_INVALID})

        if not password_reset_token.check_token(user, token):
            raise ValidationError({"detail": EmailMessages.PASSWORD_RESET_INVALID})

        user.set_password(password)
        user.save(update_fields=["password"])
        return user
    
    @staticmethod
    def validate_password_reset(uidb64: str, token: str) -> bool:
        user = EmailService.get_user_by_uid(uidb64)

        if user.is_deleted or user.is_blocked:
            raise ValidationError({"detail": EmailMessages.PASSWORD_RESET_INVALID})

        if not password_reset_token.check_token(user, token):
            raise ValidationError({"detail": EmailMessages.PASSWORD_RESET_INVALID})

        return True


 