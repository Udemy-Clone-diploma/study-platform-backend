from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect
from django.test import RequestFactory
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import ModeratorProfile, StudentProfile, TeacherProfile, User

from ._factories import authenticate_as_admin, make_user


class ModeratorProfileAdminTests(APITestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.profile_admin = admin.site._registry[ModeratorProfile]
        self.user_admin = admin.site._registry[User]

    def test_user_field_uses_autocomplete_limited_to_moderator_users(self):
        moderator = make_user(role=User.RoleChoices.MODERATOR, email="mod@example.com")
        student = make_user(role=User.RoleChoices.STUDENT, email="student@example.com")
        request = self.factory.get("/admin/users/moderatorprofile/add/")

        field = self.profile_admin.formfield_for_foreignkey(
            ModeratorProfile._meta.get_field("user"),
            request,
        )

        self.assertIsInstance(field.widget, AutocompleteSelect)
        self.assertIn(moderator, field.queryset)
        self.assertNotIn(student, field.queryset)

    def test_user_autocomplete_shows_only_available_moderator_users(self):
        available = make_user(
            role=User.RoleChoices.MODERATOR,
            email="available@example.com",
        )
        linked = make_user(role=User.RoleChoices.MODERATOR, email="linked@example.com")
        student = make_user(role=User.RoleChoices.STUDENT, email="student@example.com")
        ModeratorProfile.objects.create(user=linked, level="senior")
        request = self.factory.get(
            "/admin/autocomplete/",
            {
                "app_label": "users",
                "model_name": "moderatorprofile",
                "field_name": "user",
                "term": "",
            },
        )

        queryset, _ = self.user_admin.get_search_results(request, User.objects.all(), "")

        self.assertIn(available, queryset)
        self.assertNotIn(linked, queryset)
        self.assertNotIn(student, queryset)


class UserRegistrationTests(APITestCase):
    def setUp(self):
        authenticate_as_admin(self.client)
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

    def test_admin_create_respects_role(self):
        data = {**self.valid_data, "email": "teach@example.com", "role": "teacher"}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "teacher")
        self.assertIsNotNone(response.data["profile"])

    def test_admin_created_user_is_email_verified(self):
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=self.valid_data["email"])
        self.assertTrue(user.is_email_verified)

    def test_admin_create_moderator_gets_profile_with_default_level(self):
        data = {**self.valid_data, "email": "mod@example.com", "role": "moderator"}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["profile"]["level"], "junior")

    def test_admin_create_administrator_has_null_profile(self):
        data = {**self.valid_data, "email": "adm@example.com", "role": "administrator"}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["profile"])

    def test_create_with_soft_deleted_email_returns_400(self):
        make_user(email=self.valid_data["email"], is_deleted=True)
        response = self.client.post(self.url, self.valid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserRetrieveTests(APITestCase):
    def setUp(self):
        authenticate_as_admin(self.client)
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass",
            role="student",
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
        StudentProfile.objects.create(
            user=self.user,
            learning_goals="learn python",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["profile"])
        self.assertEqual(response.data["profile"]["learning_goals"], "learn python")

    def test_retrieve_not_found(self):
        response = self.client.get(reverse("users-detail", args=[99999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UserUpdateTests(APITestCase):
    def setUp(self):
        authenticate_as_admin(self.client)
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass",
            role="student",
        )
        self.url = reverse("users-detail", args=[self.user.pk])

    def test_update_language(self):
        response = self.client.patch(self.url, {"language": "uk"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["language"], "uk")

    def test_update_duplicate_email(self):
        User.objects.create_user(
            email="other@example.com",
            password="pass",
            role="student",
        )
        response = self.client.patch(self.url, {"email": "other@example.com"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_change_role(self):
        response = self.client.patch(self.url, {"role": "teacher"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "teacher")

    def test_role_change_materializes_new_profile(self):
        response = self.client.patch(self.url, {"role": "teacher"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["profile"])
        self.assertTrue(TeacherProfile.objects.filter(user=self.user).exists())

    def test_update_invalid_role(self):
        response = self.client.patch(self.url, {"role": "superhero"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_returns_full_user(self):
        response = self.client.patch(self.url, {"first_name": "New"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in ("id", "email", "role", "status", "is_blocked", "profile"):
            self.assertIn(key, response.data)

    def test_update_email_collides_with_soft_deleted_returns_400(self):
        make_user(email="ghost@example.com", is_deleted=True)
        response = self.client.patch(
            self.url, {"email": "ghost@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserDeleteTests(APITestCase):
    def setUp(self):
        self.admin = authenticate_as_admin(self.client)
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass",
            role="student",
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

    def test_admin_cannot_delete_self(self):
        response = self.client.delete(
            reverse("users-detail", args=[self.admin.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_deleted)

    def test_admin_can_delete_another_admin(self):
        other = make_user(role="administrator", email="admin2@example.com")
        response = self.client.delete(reverse("users-detail", args=[other.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class UserBlockTests(APITestCase):
    def setUp(self):
        self.admin = authenticate_as_admin(self.client)
        self.user = User.objects.create_user(
            email="test@example.com",
            password="pass",
            role="student",
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

    def test_block_without_body_returns_400(self):
        response = self.client.patch(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_blocked)

    def test_admin_cannot_block_self(self):
        url = reverse("users-block", args=[self.admin.pk])
        response = self.client.patch(url, {"is_blocked": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_blocked)


class UserRestoreTests(APITestCase):
    def setUp(self):
        self.admin = authenticate_as_admin(self.client)
        self.deleted = make_user(
            email="ghost@example.com", is_deleted=True, status="inactive"
        )
        self.url = reverse("users-restore", args=[self.deleted.pk])

    def test_deleted_users_listed_by_default_and_narrowed_by_param(self):
        default = self.client.get(reverse("users-list"))
        emails = [row["email"] for row in default.data["results"]]
        self.assertIn("ghost@example.com", emails)

        deleted = self.client.get(reverse("users-list"), {"is_deleted": "true"})
        self.assertEqual(
            [row["email"] for row in deleted.data["results"]],
            ["ghost@example.com"],
        )

    def test_restore_returns_full_user(self):
        response = self.client.patch(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "ghost@example.com")
        self.assertEqual(response.data["status"], "inactive")
        self.assertFalse(response.data["is_deleted"])
        self.deleted.refresh_from_db()
        self.assertFalse(self.deleted.is_deleted)

    def test_restored_user_reappears_in_default_list(self):
        self.client.patch(self.url)
        response = self.client.get(reverse("users-list"))
        emails = [row["email"] for row in response.data["results"]]
        self.assertIn("ghost@example.com", emails)


class UserProfileUpdateTests(APITestCase):
    """Admin endpoint /users/{id}/profile/ updates another user's profile."""

    def setUp(self):
        self.student = User.objects.create_user(
            email="student@example.com", password="pass", role="student"
        )
        self.teacher = User.objects.create_user(
            email="teacher@example.com", password="pass", role="teacher"
        )
        self.admin = make_user(role="administrator", email="admin_p@example.com")
        self.client.force_authenticate(user=self.admin)

    def test_update_student_profile_creates_if_missing(self):
        url = reverse("users-profile", args=[self.student.pk])
        response = self.client.patch(
            url, {"education_level": "bachelor"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["education_level"], "bachelor")

    def test_update_student_profile_updates_existing(self):
        StudentProfile.objects.create(user=self.student, education_level="bachelor")
        url = reverse("users-profile", args=[self.student.pk])
        response = self.client.patch(
            url, {"education_level": "master"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["education_level"], "master")

    def test_update_teacher_profile(self):
        url = reverse("users-profile", args=[self.teacher.pk])
        response = self.client.patch(
            url, {"specialization": "Python"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["specialization"], "Python")

    def test_update_profile_unavailable_for_administrator(self):
        url = reverse("users-profile", args=[self.admin.pk])
        response = self.client.patch(url, {"some_field": "value"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserViewSetAccessTests(APITestCase):
    """Only administrators may access the /users/ endpoints."""

    def setUp(self):
        self.target = make_user(role="student", email="target@example.com")

    def test_anonymous_cannot_list_users(self):
        response = self.client.get(reverse("users-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_cannot_list_users(self):
        self.client.force_authenticate(user=make_user(role="student", email="s@e.com"))
        response = self.client.get(reverse("users-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_cannot_list_users(self):
        self.client.force_authenticate(user=make_user(role="teacher", email="t@e.com"))
        response = self.client.get(reverse("users-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_users(self):
        authenticate_as_admin(self.client)
        response = self.client.get(reverse("users-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def _endpoint_calls(self):
        detail = reverse("users-detail", args=[self.target.pk])
        return [
            ("get", reverse("users-list"), None),
            ("get", detail, None),
            ("post", reverse("users-list"), {"email": "new@example.com"}),
            ("patch", detail, {"first_name": "X"}),
            ("delete", detail, None),
            (
                "patch",
                reverse("users-block", args=[self.target.pk]),
                {"is_blocked": True},
            ),
            ("patch", reverse("users-restore", args=[self.target.pk]), None),
        ]

    def _assert_all_endpoints_status(self, expected):
        for method, url, data in self._endpoint_calls():
            response = getattr(self.client, method)(url, data, format="json")
            self.assertEqual(
                response.status_code, expected, f"{method.upper()} {url}"
            )

    def test_anonymous_gets_401_on_every_endpoint(self):
        self._assert_all_endpoints_status(status.HTTP_401_UNAUTHORIZED)

    def test_student_gets_403_on_every_endpoint(self):
        self.client.force_authenticate(
            user=make_user(role="student", email="s2@e.com")
        )
        self._assert_all_endpoints_status(status.HTTP_403_FORBIDDEN)

    def test_teacher_gets_403_on_every_endpoint(self):
        self.client.force_authenticate(
            user=make_user(role="teacher", email="t2@e.com")
        )
        self._assert_all_endpoints_status(status.HTTP_403_FORBIDDEN)

    def test_moderator_gets_403_on_every_endpoint(self):
        self.client.force_authenticate(
            user=make_user(role="moderator", email="m2@e.com")
        )
        self._assert_all_endpoints_status(status.HTTP_403_FORBIDDEN)
