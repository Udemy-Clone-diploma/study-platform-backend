from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.users.models import User

from ._factories import make_category, make_course, make_teacher


class CourseRetrieveVisibilityTests(APITestCase):
    """Non-published courses must only be visible to owner/administrator/moderator."""

    @classmethod
    def setUpTestData(cls):
        cls.category = make_category()
        _, cls.owner_profile = make_teacher(email="owner@example.com")
        _, cls.other_teacher = make_teacher(email="other@example.com")
        cls.draft = make_course(
            cls.owner_profile,
            title="Draft",
            slug="draft-course",
            category=cls.category,
            status=Course.StatusChoices.DRAFT,
        )
        cls.published = make_course(
            cls.owner_profile,
            title="Public",
            slug="public-course",
            category=cls.category,
            status=Course.StatusChoices.PUBLISHED,
        )

    def _detail(self, course):
        return self.client.get(reverse("courses-detail", args=[course.slug]))

    def test_anonymous_can_view_published(self):
        response = self._detail(self.published)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_view_draft(self):
        response = self._detail(self.draft)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_teacher_cannot_view_draft(self):
        self.client.force_authenticate(user=self.other_teacher.user)
        response = self._detail(self.draft)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_view_own_draft(self):
        self.client.force_authenticate(user=self.owner_profile.user)
        response = self._detail(self.draft)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_administrator_can_view_any_draft(self):
        admin = User.objects.create_user(
            email="admin_view@example.com",
            password="pass12345",
            role="administrator",
        )
        self.client.force_authenticate(user=admin)
        response = self._detail(self.draft)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_moderator_can_view_any_draft(self):
        moderator = User.objects.create_user(
            email="moderator_view@example.com",
            password="pass12345",
            role="moderator",
        )
        self.client.force_authenticate(user=moderator)
        response = self._detail(self.draft)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_cannot_view_draft(self):
        student = User.objects.create_user(
            email="student_view@example.com",
            password="pass12345",
            role="student",
        )
        self.client.force_authenticate(user=student)
        response = self._detail(self.draft)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
