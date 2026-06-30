from django.core import mail
from rest_framework.test import APITestCase

from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.services import NotificationService
from apps.notifications.tasks import send_notification_email

from ._factories import make_user


class NotificationServiceCreateTests(APITestCase):
    """`create` is the single-recipient path: it gates the in-app row and the
    email on the recipient's resolved channel preferences."""

    def setUp(self):
        self.user = make_user("svc_create@example.com")

    def test_creates_row_without_email_when_email_default_off(self):
        # new_message default: in_app True, email False.
        notification = NotificationService.create(
            recipient=self.user,
            type=Notification.TypeChoices.NEW_MESSAGE,
            title="Hi",
            body="There",
        )

        self.assertIsNotNone(notification)
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_sends_email_when_email_default_on(self):
        # homework_graded default: in_app True, email True.
        notification = NotificationService.create(
            recipient=self.user,
            type=Notification.TypeChoices.HOMEWORK_GRADED,
            title="Graded",
            body="You passed",
            link_url="/learn/x",
        )

        self.assertIsNotNone(notification)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertEqual(mail.outbox[0].subject, "Graded")

    def test_in_app_disabled_returns_none_and_skips_email(self):
        NotificationPreference.objects.create(
            user=self.user, overrides={"homework_graded": {"in_app": False}}
        )

        notification = NotificationService.create(
            recipient=self.user,
            type=Notification.TypeChoices.HOMEWORK_GRADED,
            title="Graded",
            body="b",
        )

        self.assertIsNone(notification)
        self.assertEqual(Notification.objects.count(), 0)
        # in_app off short-circuits before the email gate, despite email default on.
        self.assertEqual(len(mail.outbox), 0)

    def test_email_override_enables_delivery(self):
        NotificationPreference.objects.create(
            user=self.user, overrides={"new_message": {"email": True}}
        )

        NotificationService.create(
            recipient=self.user,
            type=Notification.TypeChoices.NEW_MESSAGE,
            title="Hi",
            body="b",
        )

        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)


class NotificationServiceFanOutTests(APITestCase):
    def setUp(self):
        self.a = make_user("fan_a@example.com")
        self.b = make_user("fan_b@example.com")
        self.c = make_user("fan_c@example.com")

    def test_per_user_overrides_gate_rows_and_emails_independently(self):
        # homework_graded default: in_app True, email True.
        NotificationPreference.objects.create(
            user=self.b, overrides={"homework_graded": {"in_app": False}}
        )
        NotificationPreference.objects.create(
            user=self.c, overrides={"homework_graded": {"email": False}}
        )

        NotificationService.fan_out(
            recipients=[self.a, self.b, self.c],
            type=Notification.TypeChoices.HOMEWORK_GRADED,
            title="t",
            body="b",
        )

        # In-app rows for a and c; b opted out of in_app.
        recipients = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {self.a.id, self.c.id})

        # Emails for a and b; c opted out of email.
        emails = sorted(message.to[0] for message in mail.outbox)
        self.assertEqual(emails, sorted([self.a.email, self.b.email]))

    def test_empty_recipients_is_noop(self):
        NotificationService.fan_out(
            recipients=[],
            type=Notification.TypeChoices.HOMEWORK_GRADED,
            title="t",
            body="b",
        )

        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)


class SendNotificationEmailTests(APITestCase):
    def test_appends_frontend_url_when_link_present(self):
        send_notification_email(
            email="x@example.com", title="T", body="Body", link_url="/go"
        )

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "T")
        self.assertEqual(message.to, ["x@example.com"])
        self.assertIn("Body", message.body)
        self.assertIn("/go", message.body)

    def test_body_unchanged_when_no_link(self):
        send_notification_email(
            email="x@example.com", title="T", body="Body", link_url=None
        )

        self.assertEqual(mail.outbox[0].body, "Body")
