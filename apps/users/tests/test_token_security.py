from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.users.models import User


class TokenRefreshSecurityTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-refresh")
        self.user = User.all_objects.create_user(
            email="sectest@example.com",
            password="pass12345",
            role="student",
            is_email_verified=True,
        )
        self.refresh_token = str(RefreshToken.for_user(self.user))

    def test_refresh_missing_token(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_invalid_token(self):
        response = self.client.post(self.url, {"refresh": "invalid.token.here"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_blocked_user(self):
        self.user.is_blocked = True
        self.user.save()
        response = self.client.post(self.url, {"refresh": self.refresh_token})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_deleted_user(self):
        self.user.is_deleted = True
        self.user.save()
        response = self.client.post(self.url, {"refresh": self.refresh_token})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blocked_user_cannot_access_me_endpoint(self):
        access_token = str(AccessToken.for_user(self.user))
        self.user.is_blocked = True
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_deleted_user_cannot_access_me_endpoint(self):
        access_token = str(AccessToken.for_user(self.user))
        self.user.is_deleted = True
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_role_changed_token_is_rejected(self):
        """Access token issued with old role must be rejected after role change."""
        refresh = RefreshToken.for_user(self.user)
        refresh["role"] = self.user.role
        access_token = str(refresh.access_token)

        self.user.role = "teacher"
        self.user.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
