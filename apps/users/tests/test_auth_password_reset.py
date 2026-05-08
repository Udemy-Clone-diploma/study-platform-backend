from unittest.mock import patch

from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.tokens import password_reset_token

from ._factories import make_user


def _uid_and_token(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = password_reset_token.make_token(user)
    return uid, token


class PasswordResetRequestTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-password-reset")
        self.user = make_user(role="student", email="reset@example.com")

    def test_request_for_existing_user_sends_email(self):
        with patch(
            "apps.users.services.email_service.EmailService.send_password_reset_email"
        ) as send:
            response = self.client.post(self.url, {"email": self.user.email})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send.assert_called_once_with(self.user)

    def test_request_for_unknown_email_does_not_leak(self):
        with patch(
            "apps.users.services.email_service.EmailService.send_password_reset_email"
        ) as send:
            response = self.client.post(self.url, {"email": "nobody@example.com"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send.assert_not_called()

    def test_request_for_unverified_user_no_email(self):
        unverified = make_user(
            role="student", email="raw@example.com", verified=False
        )

        with patch(
            "apps.users.services.email_service.EmailService.send_password_reset_email"
        ) as send:
            response = self.client.post(self.url, {"email": unverified.email})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send.assert_not_called()


class PasswordResetValidateTests(APITestCase):
    def setUp(self):
        self.user = make_user(role="student", email="resetv@example.com")

    def test_valid_token_returns_200(self):
        uid, token = _uid_and_token(self.user)

        response = self.client.get(
            reverse("auth-password-reset-validate", args=[uid, token])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])

    def test_invalid_token_returns_400_with_valid_false(self):
        uid, _ = _uid_and_token(self.user)

        response = self.client.get(
            reverse("auth-password-reset-validate", args=[uid, "bogus"])
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["valid"])


class PasswordResetConfirmTests(APITestCase):
    def setUp(self):
        self.user = make_user(role="student", email="confirm@example.com")

    def _confirm_url(self, user=None):
        target = user or self.user
        uid, token = _uid_and_token(target)
        return reverse("auth-password-reset-confirm", args=[uid, token])

    def test_confirm_changes_password(self):
        url = self._confirm_url()

        response = self.client.post(url, {"password": "NewStrongPass456"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPass456"))

    def test_confirm_with_invalid_token_returns_400(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        url = reverse("auth-password-reset-confirm", args=[uid, "bogus"])

        response = self.client.post(url, {"password": "NewStrongPass456"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password("NewStrongPass456"))

    def test_confirm_token_one_use_after_password_change(self):
        """The token's hash uses user.password, so a second use must fail."""
        url = self._confirm_url()

        first = self.client.post(url, {"password": "NewStrongPass456"})
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = self.client.post(url, {"password": "AnotherPass789"})
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_short_password_rejected(self):
        url = self._confirm_url()

        response = self.client.post(url, {"password": "short"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
