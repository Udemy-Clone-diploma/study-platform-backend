from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User


class UserRegistrationTests(APITestCase):
    def setUp(self):
        self.url = reverse("users-list")
        self.valid_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "StrongPass123",
            "role": "student",
        }

    def test_register_success(self):
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], self.valid_data["email"])
        self.assertNotIn("password", response.data)

    def test_register_duplicate_email(self):
        self.client.post(self.url, self.valid_data)
        data = {**self.valid_data, "username": "anotheruser"}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_username(self):
        self.client.post(self.url, self.valid_data)
        data = {**self.valid_data, "email": "another@example.com"}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_password(self):
        data = {**self.valid_data}
        data.pop("password")
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserRetrieveTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com",
            password="pass", role="student",
        )
        self.url = reverse("users-detail", args=[self.user.pk])

    def test_retrieve_user(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)

    def test_retrieve_not_found(self):
        response = self.client.get(reverse("users-detail", args=[99999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UserUpdateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com",
            password="pass", role="student",
        )
        self.url = reverse("users-detail", args=[self.user.pk])

    def test_update_language(self):
        response = self.client.patch(self.url, {"language": "uk"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["language"], "uk")

    def test_update_duplicate_email(self):
        User.objects.create_user(
            username="other", email="other@example.com",
            password="pass", role="student",
        )
        response = self.client.patch(self.url, {"email": "other@example.com"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_duplicate_username(self):
        User.objects.create_user(
            username="other", email="other@example.com",
            password="pass", role="student",
        )
        response = self.client.patch(self.url, {"username": "other"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserDeleteTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com",
            password="pass", role="student",
        )
        self.url = reverse("users-detail", args=[self.user.pk])

    def test_delete_user(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())


class UserBlockTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com",
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
