from unittest.mock import patch

from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User
from apps.users.tokens import email_verification_token

from ._factories import make_user


def _uid_and_token(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    return uid, token


class VerifyEmailTests(APITestCase):
    def setUp(self):
        self.user = User.all_objects.create_user(
            email="verify@example.com",
            password="pass12345",
            role="student",
            is_email_verified=False,
        )

    def test_valid_token_marks_user_verified(self):
        uid, token = _uid_and_token(self.user)

        response = self.client.get(
            reverse("auth-verify-email", args=[uid, token])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_invalid_token_returns_400(self):
        uid, _ = _uid_and_token(self.user)

        response = self.client.get(
            reverse("auth-verify-email", args=[uid, "totally-bogus"])
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_email_verified)

    def test_invalid_uid_returns_400(self):
        _, token = _uid_and_token(self.user)

        response = self.client.get(
            reverse("auth-verify-email", args=["bad-uid", token])
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_invalidated_once_user_verified(self):
        """The token's hash uses is_email_verified, so verifying twice fails."""
        uid, token = _uid_and_token(self.user)

        first = self.client.get(reverse("auth-verify-email", args=[uid, token]))
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = self.client.get(reverse("auth-verify-email", args=[uid, token]))
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deleted_user_cannot_verify(self):
        self.user.is_deleted = True
        self.user.save()
        uid, token = _uid_and_token(self.user)

        response = self.client.get(reverse("auth-verify-email", args=[uid, token]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ResendVerificationTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-resend-verification")

    def test_resend_for_unverified_user_sends_email(self):
        user = make_user(role="student", email="unverif@example.com", verified=False)

        with patch(
            "apps.users.services.email_service.EmailService.send_verification_email"
        ) as send:
            response = self.client.post(self.url, {"email": user.email})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send.assert_called_once_with(user)

    def test_resend_for_already_verified_user_no_email_sent(self):
        user = make_user(role="student", email="verif@example.com", verified=True)

        with patch(
            "apps.users.services.email_service.EmailService.send_verification_email"
        ) as send:
            response = self.client.post(self.url, {"email": user.email})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send.assert_not_called()

    def test_resend_for_unknown_email_does_not_leak(self):
        with patch(
            "apps.users.services.email_service.EmailService.send_verification_email"
        ) as send:
            response = self.client.post(
                self.url, {"email": "nobody@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send.assert_not_called()
