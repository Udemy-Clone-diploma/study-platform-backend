from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User


class UserRegistrationTests(APITestCase):
    def setUp(self):
        self.url = reverse("users-list")
        self.valid_data = {
            "email": "test@example.com",
            "password": "StrongPass123",
            "first_name": "John",
            "last_name": "Doe",
            "role": "student",
        }

    def test_register_success(self):
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], self.valid_data["email"])
        self.assertNotIn("password", response.data)
        self.assertIsNotNone(response.data["profile"])

    def test_register_duplicate_email(self):
        self.client.post(self.url, self.valid_data)
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_password(self):
        data = {**self.valid_data}
        data.pop("password")
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserRetrieveTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass", role="student",
        )
        self.url = reverse("users-detail", args=[self.user.pk])

    def test_retrieve_user(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertIn("profile", response.data)

    def test_retrieve_user_profile_none_without_student_profile(self):
        response = self.client.get(self.url)
        self.assertIsNone(response.data["profile"])

    def test_retrieve_user_with_student_profile(self):
        from apps.users.models import StudentProfile
        StudentProfile.objects.create(
            user=self.user, education_level="bachelor", learning_goals="learn python"
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["profile"])
        self.assertEqual(response.data["profile"]["education_level"], "bachelor")

    def test_retrieve_not_found(self):
        response = self.client.get(reverse("users-detail", args=[99999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UserUpdateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass", role="student",
        )
        self.url = reverse("users-detail", args=[self.user.pk])

    def test_update_language(self):
        response = self.client.patch(self.url, {"language": "uk"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["language"], "uk")

    def test_update_duplicate_email(self):
        User.objects.create_user(
            email="other@example.com",
            password="pass", role="student",
        )
        response = self.client.patch(self.url, {"email": "other@example.com"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserDeleteTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass", role="student",
        )
        self.url = reverse("users-detail", args=[self.user.pk])

    def test_soft_delete_user(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_deleted)
        self.assertEqual(self.user.status, "inactive")

    def test_deleted_user_not_visible(self):
        self.client.delete(self.url)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UserBlockTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass", role="student",
        )
        self.url = reverse("users-block", args=[self.user.pk])

    def test_block_user(self):
        response = self.client.patch(self.url, {"is_blocked": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_blocked"])
        self.assertEqual(response.data["status"], "inactive")

    def test_unblock_user(self):
        self.user.is_blocked = True
        self.user.save()
        response = self.client.patch(self.url, {"is_blocked": False}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_blocked"])
        self.assertEqual(response.data["status"], "active")


class UserProfileUpdateTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="student@example.com",
            password="pass", role="student",
        )
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="pass", role="teacher",
        )
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="pass", role="administrator",
        )

    def test_update_student_profile_creates_if_missing(self):
        url = reverse("users-profile", args=[self.student.pk])
        response = self.client.patch(url, {"education_level": "bachelor"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["education_level"], "bachelor")

    def test_update_student_profile_updates_existing(self):
        from apps.users.models import StudentProfile
        StudentProfile.objects.create(user=self.student, education_level="bachelor")
        url = reverse("users-profile", args=[self.student.pk])
        response = self.client.patch(url, {"education_level": "master"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["education_level"], "master")

    def test_update_teacher_profile(self):
        url = reverse("users-profile", args=[self.teacher.pk])
        response = self.client.patch(url, {"specialization": "Python"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["specialization"], "Python")

    def test_update_profile_unavailable_for_administrator(self):
        url = reverse("users-profile", args=[self.admin.pk])
        response = self.client.patch(url, {"some_field": "value"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
