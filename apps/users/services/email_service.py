from datetime import datetime
from email.message import MIMEPart
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.users.email_content import get_email_content, resolve_email_locale
from apps.users.tokens import email_verification_token, password_reset_token, teacher_invitation_token

COMPANY_NAME = "Nexo4You"
LOGO_PATH = Path(settings.BASE_DIR) / "apps" / "common" / "assets" / "logo" / "nexo4u_logo.png"


class EmailService:
    @classmethod
    def _send_branded_email(
        cls,
        *,
        recipient: str,
        language: str | None,
        email_type: str,
        name: str,
        cta_url: str | None = None,
        extra_paragraphs: list[str] | None = None,
    ) -> None:
        locale = resolve_email_locale(language)
        content = get_email_content(email_type, locale)

        greeting = content["greeting"].format(name=name)
        paragraphs = list(content["paragraphs"]) + list(extra_paragraphs or [])
        cta_label = content["cta_label"] if cta_url else None
        expiry_note = content["expiry_note"] if cta_url else None

        context = {
            "locale": locale,
            "subject": content["subject"],
            "heading": content["heading"],
            "greeting": greeting,
            "paragraphs": paragraphs,
            "cta_url": cta_url,
            "cta_label": cta_label,
            "expiry_note": expiry_note,
            "footer_note": content["footer_note"],
            "company_name": COMPANY_NAME,
            "year": datetime.now().year,
        }

        html_body = render_to_string("emails/base_email.html", context)
        text_lines = [content["heading"], "", greeting, *paragraphs]
        if cta_url:
            text_lines += ["", f"{cta_label}: {cta_url}"]
            if expiry_note:
                text_lines += ["", expiry_note]
        text_lines += ["", content["footer_note"]]
        text_body = "\n".join(text_lines)

        message = EmailMultiAlternatives(
            subject=content["subject"],
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        message.attach_alternative(html_body, "text/html")

        logo = MIMEPart()
        logo.set_content(
            LOGO_PATH.read_bytes(),
            maintype="image",
            subtype="png",
            disposition="inline",
            filename=LOGO_PATH.name,
            cid="<logo>",
        )
        message.attach(logo)

        message.send()

    @classmethod
    def send_verification_email(cls, user) -> None:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        url = f"{settings.FRONTEND_URL}/register/verify-email/{uid}/{token}/"

        cls._send_branded_email(
            recipient=user.email,
            language=user.language,
            email_type="verification",
            name=user.first_name or user.email,
            cta_url=url,
        )

    @classmethod
    def send_password_reset_email(cls, user) -> None:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = password_reset_token.make_token(user)
        url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

        cls._send_branded_email(
            recipient=user.email,
            language=user.language,
            email_type="password_reset",
            name=user.first_name or user.email,
            cta_url=url,
        )

    @classmethod
    def send_teacher_invitation_email(cls, user) -> None:
        """The one email sent after a teacher application is approved.

        A single link both confirms the email and lets the teacher set their
        own password — no generated password is ever emailed.
        """
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = teacher_invitation_token.make_token(user)
        url = f"{settings.FRONTEND_URL}/activate-teacher-account/{uid}/{token}/"

        cls._send_branded_email(
            recipient=user.email,
            language=user.language,
            email_type="teacher_invitation",
            name=user.first_name or user.email,
            cta_url=url,
        )

    @classmethod
    def send_teacher_application_cancelled_email(cls, application) -> None:
        content = get_email_content("teacher_application_cancelled", None)
        extra_paragraphs = []
        if application.moderator_comment:
            extra_paragraphs.append(
                f"{content['moderator_comment_label']} {application.moderator_comment}"
            )

        cls._send_branded_email(
            recipient=application.email,
            language=None,
            email_type="teacher_application_cancelled",
            name=application.first_name or application.email,
            extra_paragraphs=extra_paragraphs,
        )
