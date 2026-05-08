from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import StudentProfile, TeacherProfile, ModeratorProfile

from ._factories import make_user


class MeEndpointTests(APITestCase):
    """GET/PATCH /auth/me/ acts on the authenticated user."""

    def setUp(self):
        self.url = reverse("auth-me")
        self.user = make_user(role="student", email="me@example.com")

    def test_anonymous_cannot_access(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_returns_current_user(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["id"], self.user.pk)

    def test_patch_updates_current_user_fields(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url, {"first_name": "Updated", "language": "uk"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "Updated")
        self.assertEqual(response.data["language"], "uk")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")


class MeProfileTeacherTests(APITestCase):
    """PATCH /auth/me/profile/teacher/ updates the caller's TeacherProfile."""

    def setUp(self):
        self.url = reverse("auth-me-profile-teacher")
        self.teacher = make_user(role="teacher", email="t-prof@example.com")
        self.student = make_user(role="student", email="s-prof@example.com")

    def test_teacher_can_update_own_profile(self):
        self.client.force_authenticate(user=self.teacher)

        response = self.client.patch(
            self.url,
            {"specialization": "Backend", "bio": "Hello", "experience": 5},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["specialization"], "Backend")
        self.assertTrue(TeacherProfile.objects.filter(user=self.teacher).exists())

    def test_student_gets_403_on_teacher_endpoint(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.patch(
            self.url, {"specialization": "Hack"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_gets_401(self):
        response = self.client.patch(
            self.url, {"specialization": "x"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MeProfileStudentTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-me-profile-student")
        self.student = make_user(role="student", email="s2-prof@example.com")
        self.teacher = make_user(role="teacher", email="t2-prof@example.com")

    def test_student_can_update_own_profile(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.patch(
            self.url, {"education_level": "bachelor"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["education_level"], "bachelor")
        self.assertTrue(StudentProfile.objects.filter(user=self.student).exists())

    def test_teacher_gets_403_on_student_endpoint(self):
        self.client.force_authenticate(user=self.teacher)

        response = self.client.patch(
            self.url, {"education_level": "bachelor"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class MeProfileModeratorTests(APITestCase):
    def setUp(self):
        self.url = reverse("auth-me-profile-moderator")
        self.moderator = make_user(role="moderator", email="m-prof@example.com")
        self.student = make_user(role="student", email="s3-prof@example.com")
        # ModeratorProfile.level has no default and is required; pre-create with
        # an initial value so update_profile's get_or_create() does not blow up.
        ModeratorProfile.objects.create(user=self.moderator, level="junior")

    def test_moderator_can_update_own_profile(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.patch(self.url, {"level": "senior"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["level"], "senior")

    def test_student_gets_403_on_moderator_endpoint(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.patch(self.url, {"level": "senior"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
