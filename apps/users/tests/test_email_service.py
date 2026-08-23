from django.test import TestCase

from apps.users.email_content import resolve_email_locale
from apps.users.models import TeacherApplication
from apps.users.services.email_service import EmailService

from ._factories import make_user


class ResolveEmailLocaleTests(TestCase):
    def test_supported_locale_passes_through(self):
        self.assertEqual(resolve_email_locale("uk"), "uk")
        self.assertEqual(resolve_email_locale("es"), "es")

    def test_unsupported_or_missing_locale_falls_back_to_english(self):
        self.assertEqual(resolve_email_locale("ru"), "en")
        self.assertEqual(resolve_email_locale(None), "en")
        self.assertEqual(resolve_email_locale(""), "en")


class VerificationEmailContentTests(TestCase):
    def test_renders_in_users_language(self):
        user = make_user(role="student", email="olena@example.com", language="uk", first_name="Олена")

        EmailService.send_verification_email(user)

        message = self.get_last_message()
        self.assertEqual(message.subject, "Підтвердіть свою електронну адресу")
        self.assertIn("Олена", message.body)
        self.assertEqual(len(message.alternatives), 1)
        html_body, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("Підтвердити Email", html_body)
        self.assertIn("cid:logo", html_body)
        self.assertIn("register/verify-email/", html_body)
        self.assertEqual(len(message.attachments), 1)
        self.assertEqual(message.attachments[0].get("Content-ID"), "<logo>")

    def test_unsupported_language_falls_back_to_english(self):
        user = make_user(role="student", email="foo@example.com", language="xx", first_name="Foo")

        EmailService.send_verification_email(user)

        message = self.get_last_message()
        self.assertEqual(message.subject, "Confirm your email address")

    def get_last_message(self):
        from django.core import mail

        return mail.outbox[-1]


class PasswordResetEmailContentTests(TestCase):
    def test_renders_in_users_language(self):
        user = make_user(role="student", email="foo@example.com", language="es", first_name="Foo")

        EmailService.send_password_reset_email(user)

        from django.core import mail

        message = mail.outbox[-1]
        self.assertEqual(message.subject, "Restablece tu contraseña")
        self.assertIn("reset-password/", message.alternatives[0][0])


class TeacherInvitationEmailContentTests(TestCase):
    def test_has_no_expiry_note_and_uses_language(self):
        user = make_user(role="teacher", email="teach@example.com", language="fr", first_name="Marie")

        EmailService.send_teacher_invitation_email(user)

        from django.core import mail

        message = mail.outbox[-1]
        self.assertEqual(
            message.subject, "Félicitations ! Votre candidature d'enseignant a été approuvée"
        )
        self.assertIn("activate-teacher-account/", message.alternatives[0][0])


class TeacherApplicationCancelledEmailContentTests(TestCase):
    def _make_application(self, **overrides):
        return TeacherApplication.objects.create(
            first_name="Ivan",
            last_name="Petrenko",
            email="ivan@example.com",
            **overrides,
        )

    def test_defaults_to_english_and_has_no_cta(self):
        application = self._make_application()

        EmailService.send_teacher_application_cancelled_email(application)

        from django.core import mail

        message = mail.outbox[-1]
        self.assertEqual(
            message.subject, "Your teacher registration application has been cancelled"
        )
        html_body = message.alternatives[0][0]
        self.assertNotIn('href="http', html_body)

    def test_includes_moderator_comment_when_present(self):
        application = self._make_application(
            moderator_comment="Please reapply with a more detailed bio."
        )

        EmailService.send_teacher_application_cancelled_email(application)

        from django.core import mail

        message = mail.outbox[-1]
        self.assertIn("Please reapply with a more detailed bio.", message.body)
        self.assertIn("Moderator comment:", message.body)

    def test_omits_moderator_comment_line_when_absent(self):
        application = self._make_application()

        EmailService.send_teacher_application_cancelled_email(application)

        from django.core import mail

        message = mail.outbox[-1]
        self.assertNotIn("Moderator comment:", message.body)
