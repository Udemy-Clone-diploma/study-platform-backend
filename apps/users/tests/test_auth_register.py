from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import StudentProfile, User


class AuthRegisterEndpointTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-register")
        self.payload = {
            "email": "new@example.com",
            "password": "StrongPass123",
            "first_name": "Jane",
            "last_name": "Roe",
            "role": "student",
        }

    def test_register_creates_user_and_student_profile(self):
        with patch(
            "apps.users.services.email_service.EmailService.send_verification_email"
        ) as send_email:
            response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=self.payload["email"])
        self.assertFalse(user.is_email_verified)
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())
        send_email.assert_called_once()

    def test_register_response_omits_password(self):
        with patch(
            "apps.users.services.email_service.EmailService.send_verification_email"
        ):
            response = self.client.post(self.url, self.payload)

        self.assertNotIn("password", response.data)

    def test_register_force_role_to_student(self):
        """Even if role=teacher is sent, registration creates a student account."""
        with patch(
            "apps.users.services.email_service.EmailService.send_verification_email"
        ):
            response = self.client.post(
                self.url, {**self.payload, "role": "teacher"}
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "student")

    def test_register_rejects_short_password(self):
        with patch(
            "apps.users.services.email_service.EmailService.send_verification_email"
        ):
            response = self.client.post(
                self.url, {**self.payload, "password": "short"}
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(
            email=self.payload["email"], password="x", role="student"
        )

        with patch(
            "apps.users.services.email_service.EmailService.send_verification_email"
        ):
            response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
