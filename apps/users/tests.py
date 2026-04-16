from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

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
        """Access token issued with old role must be rejected after role change (SCRUM-123)."""
        from rest_framework_simplejwt.tokens import RefreshToken as RT
        refresh = RT.for_user(self.user)
        refresh["role"] = self.user.role
        access_token = str(refresh.access_token)

        self.user.role = "teacher"
        self.user.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PermissionClassTests(APITestCase):
    """Unit tests for custom DRF permission classes (SCRUM-122)."""

    def _make_user(self, role, email=None):
        return User.all_objects.create_user(
            email=email or f"{role}@example.com",
            password="pass12345",
            role=role,
            is_email_verified=True,
        )

    def _request(self, user):
        """Return a fake authenticated request-like object."""
        from django.test import RequestFactory
        request = RequestFactory().get("/")
        request.user = user
        return request

    def _anon_request(self):
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        return request

    # IsAdmin
    def test_is_admin_allows_administrator(self):
        from apps.users.permissions import IsAdmin
        perm = IsAdmin()
        user = self._make_user("administrator")
        self.assertTrue(perm.has_permission(self._request(user), None))
        self.assertTrue(perm.has_object_permission(self._request(user), None, object()))

    def test_is_admin_rejects_other_roles(self):
        from apps.users.permissions import IsAdmin
        perm = IsAdmin()
        for role in ("student", "teacher", "moderator"):
            user = self._make_user(role, email=f"admin_test_{role}@example.com")
            self.assertFalse(perm.has_permission(self._request(user), None))

    def test_is_admin_rejects_anonymous(self):
        from apps.users.permissions import IsAdmin
        self.assertFalse(IsAdmin().has_permission(self._anon_request(), None))

    # IsAdminOrModerator
    def test_is_admin_or_moderator_allows_admin(self):
        from apps.users.permissions import IsAdminOrModerator
        perm = IsAdminOrModerator()
        user = self._make_user("administrator", email="aom_admin@example.com")
        self.assertTrue(perm.has_permission(self._request(user), None))

    def test_is_admin_or_moderator_allows_moderator(self):
        from apps.users.permissions import IsAdminOrModerator
        perm = IsAdminOrModerator()
        user = self._make_user("moderator", email="aom_mod@example.com")
        self.assertTrue(perm.has_permission(self._request(user), None))

    def test_is_admin_or_moderator_rejects_student_and_teacher(self):
        from apps.users.permissions import IsAdminOrModerator
        perm = IsAdminOrModerator()
        for role in ("student", "teacher"):
            user = self._make_user(role, email=f"aom_{role}@example.com")
            self.assertFalse(perm.has_permission(self._request(user), None))

    # IsTeacher
    def test_is_teacher_allows_teacher(self):
        from apps.users.permissions import IsTeacher
        perm = IsTeacher()
        user = self._make_user("teacher", email="teacher_perm@example.com")
        self.assertTrue(perm.has_permission(self._request(user), None))

    def test_is_teacher_rejects_other_roles(self):
        from apps.users.permissions import IsTeacher
        perm = IsTeacher()
        for role in ("student", "moderator", "administrator"):
            user = self._make_user(role, email=f"teacher_test_{role}@example.com")
            self.assertFalse(perm.has_permission(self._request(user), None))

    # IsStudent
    def test_is_student_allows_student(self):
        from apps.users.permissions import IsStudent
        perm = IsStudent()
        user = self._make_user("student", email="student_perm@example.com")
        self.assertTrue(perm.has_permission(self._request(user), None))

    def test_is_student_rejects_other_roles(self):
        from apps.users.permissions import IsStudent
        perm = IsStudent()
        for role in ("teacher", "moderator", "administrator"):
            user = self._make_user(role, email=f"student_test_{role}@example.com")
            self.assertFalse(perm.has_permission(self._request(user), None))

    # IsOwnerOrAdmin
    def test_is_owner_or_admin_allows_owner(self):
        from apps.users.permissions import IsOwnerOrAdmin
        perm = IsOwnerOrAdmin()
        user = self._make_user("student", email="owner@example.com")
        self.assertTrue(perm.has_object_permission(self._request(user), None, user))

    def test_is_owner_or_admin_allows_admin_on_any_object(self):
        from apps.users.permissions import IsOwnerOrAdmin
        perm = IsOwnerOrAdmin()
        admin = self._make_user("administrator", email="admin_owner@example.com")
        other = self._make_user("student", email="other_owner@example.com")
        self.assertTrue(perm.has_object_permission(self._request(admin), None, other))

    def test_is_owner_or_admin_rejects_non_owner(self):
        from apps.users.permissions import IsOwnerOrAdmin
        perm = IsOwnerOrAdmin()
        user = self._make_user("student", email="user_owner@example.com")
        other = self._make_user("teacher", email="other2_owner@example.com")
        self.assertFalse(perm.has_object_permission(self._request(user), None, other))

    def test_is_owner_or_admin_allows_owner_via_user_attr(self):
        from apps.users.permissions import IsOwnerOrAdmin

        class FakeObj:
            pass

        perm = IsOwnerOrAdmin()
        user = self._make_user("teacher", email="teacher_obj_owner@example.com")
        obj = FakeObj()
        obj.user = user
        self.assertTrue(perm.has_object_permission(self._request(user), None, obj))

    def test_is_owner_or_admin_rejects_anonymous(self):
        from apps.users.permissions import IsOwnerOrAdmin
        perm = IsOwnerOrAdmin()
        user = self._make_user("student", email="anon_owner_test@example.com")
        self.assertFalse(perm.has_object_permission(self._anon_request(), None, user))
