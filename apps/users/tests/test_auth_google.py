from unittest.mock import Mock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User

from ._factories import make_user


def _google_payload(email="newstudent@example.com", **overrides):
    payload = {
        "email": email,
        "email_verified": True,
        "given_name": "Nina",
        "family_name": "Newcomer",
        "picture": "https://example.com/photo.jpg",
    }
    payload.update(overrides)
    return payload


class AuthGoogleEndpointTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-google")

    @patch("apps.users.services.auth_service.requests.get")
    @patch("apps.users.services.auth_service.google_id_token.verify_oauth2_token")
    def test_new_user_is_created_and_email_verified(self, mock_verify, mock_get):
        mock_verify.return_value = _google_payload()
        mock_get.return_value = Mock(status_code=200, content=b"fake-image-bytes")
        mock_get.return_value.raise_for_status = Mock()

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        user = User.objects.get(email="newstudent@example.com")
        self.assertEqual(user.role, User.RoleChoices.STUDENT)
        self.assertTrue(user.is_email_verified)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.avatar)
        self.assertTrue(hasattr(user, "student_profile"))

    @patch("apps.users.services.auth_service.google_id_token.verify_oauth2_token")
    def test_existing_verified_user_logs_in(self, mock_verify):
        existing = make_user(role="student", email="known@example.com", verified=True)
        mock_verify.return_value = _google_payload(email="known@example.com")

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.filter(email="known@example.com").count(), 1)
        self.assertEqual(User.objects.get(email="known@example.com").pk, existing.pk)

    @patch("apps.users.services.auth_service.google_id_token.verify_oauth2_token")
    def test_existing_unverified_user_gets_auto_verified(self, mock_verify):
        make_user(role="student", email="pending@example.com", verified=False)
        mock_verify.return_value = _google_payload(email="pending@example.com")

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.get(email="pending@example.com").is_email_verified)

    @patch("apps.users.services.auth_service.google_id_token.verify_oauth2_token")
    def test_blocked_user_cannot_login(self, mock_verify):
        user = make_user(role="student", email="blocked@example.com", verified=True)
        user.is_blocked = True
        user.save()
        mock_verify.return_value = _google_payload(email="blocked@example.com")

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.users.services.auth_service.google_id_token.verify_oauth2_token")
    def test_deleted_user_cannot_login(self, mock_verify):
        user = make_user(role="student", email="deleted@example.com", verified=True)
        user.is_deleted = True
        user.save()
        mock_verify.return_value = _google_payload(email="deleted@example.com")

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.users.services.auth_service.google_id_token.verify_oauth2_token")
    def test_pending_teacher_invitation_cannot_login(self, mock_verify):
        make_user(
            role="teacher",
            email="invited@example.com",
            verified=False,
            status=User.StatusChoices.INACTIVE,
        )
        mock_verify.return_value = _google_payload(email="invited@example.com")

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("apps.users.services.auth_service.google_id_token.verify_oauth2_token")
    def test_invalid_token_returns_401(self, mock_verify):
        mock_verify.side_effect = ValueError("bad token")

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.users.services.auth_service.google_id_token.verify_oauth2_token")
    def test_unverified_google_email_returns_401(self, mock_verify):
        mock_verify.return_value = _google_payload(email_verified=False)

        response = self.client.post(self.url, {"id_token": "fake-token"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_id_token_returns_400(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
