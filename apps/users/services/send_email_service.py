from django.core.mail import send_mail
from django.conf import settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from apps.users.services.token_generator_service import email_verification_token


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