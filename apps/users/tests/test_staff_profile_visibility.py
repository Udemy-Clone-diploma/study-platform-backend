from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.tests._factories import make_user


class StaffProfileVisibilityTests(APITestCase):
    def setUp(self):
        self.moderator = make_user(
            role="moderator",
            email="profile-staff-moderator@example.com",
        )
        self.administrator = make_user(
            role="administrator",
            email="profile-staff-admin@example.com",
            instagram="https://instagram.com/private-admin",
            linkedin="https://linkedin.com/in/private-admin",
        )
        self.student = make_user(
            role="student",
            email="profile-staff-student@example.com",
        )

    def test_moderator_sees_administrator_as_public_user(self):
        self.client.force_authenticate(self.moderator)

        response = self.client.get(reverse("user-admin-profile", args=[self.administrator.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.administrator.pk)
        self.assertEqual(response.data["role"], "administrator")
        self.assertEqual(response.data["email"], "")
        self.assertEqual(response.data["instagram"], "")
        self.assertEqual(response.data["linkedin"], "")
        self.assertNotIn("user", response.data)
        self.assertNotIn("details", response.data)

    def test_moderator_sees_detailed_non_admin_profile(self):
        self.client.force_authenticate(self.moderator)

        response = self.client.get(reverse("user-admin-profile", args=[self.student.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["id"], self.student.pk)
        self.assertEqual(response.data["user"]["role"], "student")
        self.assertIn("student", response.data["details"])
        self.assertIn("report_stats", response.data)
