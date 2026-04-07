from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import StudentProfile, TeacherProfile, User


class RegisterTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-register")
        self.data = {
            "email": "new@example.com",
            "password": "StrongPass123",
            "first_name": "John",
            "last_name": "Doe",
            "role": "student",
        }

    def test_register_success_returns_tokens_and_user(self):
        response = self.client.post(self.url, self.data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["email"], self.data["email"])

    def test_register_auto_creates_student_profile(self):
        self.client.post(self.url, self.data, format="json")
        user = User.objects.get(email=self.data["email"])
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())

    def test_register_auto_creates_teacher_profile(self):
        data = {**self.data, "email": "teacher@example.com", "role": "teacher"}
        self.client.post(self.url, data, format="json")
        user = User.objects.get(email="teacher@example.com")
        self.assertTrue(TeacherProfile.objects.filter(user=user).exists())

    def test_register_administrator_no_profile(self):
        data = {**self.data, "email": "admin@example.com", "role": "administrator"}
        self.client.post(self.url, data, format="json")
        user = User.objects.get(email="admin@example.com")
        self.assertFalse(StudentProfile.objects.filter(user=user).exists())

    def test_register_password_not_in_response(self):
        response = self.client.post(self.url, self.data, format="json")
        self.assertNotIn("password", response.data.get("user", {}))

    def test_register_duplicate_email_returns_400(self):
        self.client.post(self.url, self.data, format="json")
        response = self.client.post(self.url, self.data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_required_fields_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-login")
        self.password = "StrongPass123"
        self.user = User.objects.create_user(
            email="test@example.com",
            password=self.password,
            role="student",
        )

    def test_login_success_returns_tokens(self):
        response = self.client.post(
            self.url, {"email": "test@example.com", "password": self.password}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_wrong_password_returns_401(self):
        response = self.client.post(
            self.url, {"email": "test@example.com", "password": "wrongpassword"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_wrong_email_returns_401(self):
        response = self.client.post(
            self.url, {"email": "nobody@example.com", "password": self.password}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_blocked_user_returns_403(self):
        self.user.is_blocked = True
        self.user.save()
        response = self.client.post(
            self.url, {"email": "test@example.com", "password": self.password}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_deleted_user_returns_403(self):
        self.user.is_deleted = True
        self.user.save()
        response = self.client.post(
            self.url, {"email": "test@example.com", "password": self.password}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_missing_fields_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TokenRefreshTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-refresh")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="StrongPass123",
            role="student",
        )
        refresh = RefreshToken.for_user(self.user)
        self.refresh_token = str(refresh)

    def test_refresh_returns_new_access_token(self):
        response = self.client.post(self.url, {"refresh": self.refresh_token}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_refresh_invalid_token_returns_401(self):
        response = self.client.post(self.url, {"refresh": "not.a.valid.token"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_missing_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="StrongPass123",
            role="student",
        )
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.url = reverse("auth-me")

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_me_unauthenticated_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user(self):
        self._auth()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertIn("profile", response.data)

    def test_me_patch_unauthenticated_returns_401(self):
        response = self.client.patch(self.url, {"language": "uk"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_patch_updates_language(self):
        self._auth()
        response = self.client.patch(self.url, {"language": "uk"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["language"], "uk")

    def test_me_patch_updates_first_name(self):
        self._auth()
        response = self.client.patch(self.url, {"first_name": "Updated"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Updated")

    def test_me_patch_duplicate_email_returns_400(self):
        User.objects.create_user(
            email="other@example.com", password="pass", role="student"
        )
        self._auth()
        response = self.client.patch(self.url, {"email": "other@example.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MeProfileTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="student@example.com", password="StrongPass123", role="student"
        )
        self.teacher = User.objects.create_user(
            email="teacher@example.com", password="StrongPass123", role="teacher"
        )
        self.admin = User.objects.create_user(
            email="admin@example.com", password="StrongPass123", role="administrator"
        )
        self.url = reverse("auth-me-profile")

    def _auth_as(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

    def test_me_profile_unauthenticated_returns_401(self):
        response = self.client.patch(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_profile_patch_creates_and_updates_student(self):
        self._auth_as(self.student)
        response = self.client.patch(self.url, {"education_level": "bachelor"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["education_level"], "bachelor")

    def test_me_profile_patch_updates_existing_student_profile(self):
        StudentProfile.objects.create(user=self.student, education_level="bachelor")
        self._auth_as(self.student)
        response = self.client.patch(self.url, {"education_level": "master"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["education_level"], "master")

    def test_me_profile_patch_teacher(self):
        self._auth_as(self.teacher)
        response = self.client.patch(self.url, {"specialization": "Python"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["specialization"], "Python")

    def test_me_profile_administrator_returns_400(self):
        self._auth_as(self.admin)
        response = self.client.patch(self.url, {"field": "value"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
