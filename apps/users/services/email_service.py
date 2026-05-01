from django.conf import settings
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.users.tokens import email_verification_token, password_reset_token


class EmailService:
    @staticmethod
    def send_verification_email(user) -> None:
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
    def send_password_reset_email(user) -> None:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = password_reset_token.make_token(user)
        url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

        send_mail(
            subject="Скидання пароля",
            message=f"Перейдіть за посиланням, щоб скинути пароль (діє 1 годину):\n{url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
