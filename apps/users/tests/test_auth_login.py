from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ._factories import make_user


class AuthLoginEndpointTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-login")
        self.user = make_user(
            role="student", email="login@example.com", verified=True
        )

    def test_login_returns_token_pair(self):
        response = self.client.post(
            self.url, {"email": self.user.email, "password": "pass12345"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_wrong_password_returns_401(self):
        response = self.client.post(
            self.url, {"email": self.user.email, "password": "wrong"}
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_with_unknown_email_returns_401(self):
        response = self.client.post(
            self.url, {"email": "ghost@example.com", "password": "pass12345"}
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unverified_email_blocks_login_with_403(self):
        unverified = make_user(
            role="student", email="unverified@example.com", verified=False
        )

        response = self.client.post(
            self.url, {"email": unverified.email, "password": "pass12345"}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_blocked_user_cannot_login(self):
        self.user.is_blocked = True
        self.user.save()

        response = self.client.post(
            self.url, {"email": self.user.email, "password": "pass12345"}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deleted_user_cannot_login(self):
        self.user.is_deleted = True
        self.user.save()

        response = self.client.post(
            self.url, {"email": self.user.email, "password": "pass12345"}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_missing_fields_returns_400(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
