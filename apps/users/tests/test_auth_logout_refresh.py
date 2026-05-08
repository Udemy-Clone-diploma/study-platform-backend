from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from ._factories import make_user


class AuthLogoutTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-logout")
        self.user = make_user(role="student", email="logout@example.com")
        self.refresh = str(RefreshToken.for_user(self.user))
        self.client.force_authenticate(user=self.user)

    def test_logout_blacklists_refresh_token(self):
        response = self.client.post(self.url, {"refresh": self.refresh})

        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)

        self.client.force_authenticate(user=None)
        refresh_response = self.client.post(
            reverse("auth-refresh"), {"refresh": self.refresh}
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.url, {"refresh": self.refresh})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_with_invalid_token_returns_400(self):
        response = self.client.post(self.url, {"refresh": "not.a.token"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_missing_token_returns_400(self):
        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AuthRefreshTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-refresh")
        self.user = make_user(role="student", email="refresh@example.com")
        self.refresh = str(RefreshToken.for_user(self.user))

    def test_refresh_returns_new_access_token(self):
        response = self.client.post(self.url, {"refresh": self.refresh})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_refresh_includes_role_in_new_access_token(self):
        from rest_framework_simplejwt.tokens import AccessToken as AT

        response = self.client.post(self.url, {"refresh": self.refresh})

        decoded = AT(response.data["access"])
        self.assertEqual(decoded["role"], self.user.role)
