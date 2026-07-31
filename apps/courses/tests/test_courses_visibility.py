from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from apps.enrollments.tests._factories import make_student
from apps.users.models import User

from ._factories import make_category, make_course, make_teacher


class CourseRetrieveVisibilityTests(APITestCase):
    """Public and full course representations have separate access rules."""

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

    def _public_detail(self, course):
        return self.client.get(reverse("courses-public", args=[course.slug]))

    def test_anonymous_cannot_view_full_published_course(self):
        response = self._detail(self.published)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anonymous_can_view_public_published_course(self):
        response = self._public_detail(self.published)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_view_public_draft(self):
        response = self._public_detail(self.draft)
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

    def test_enrolled_student_can_view_full_published_course(self):
        student_user, student_profile = make_student(
            email="enrolled_visibility@example.com",
        )
        Enrollment.objects.create(
            student_profile=student_profile,
            course=self.published,
        )
        self.client.force_authenticate(user=student_user)

        response = self._detail(self.published)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_enrolled_student_cannot_view_full_published_course(self):
        student_user, _ = make_student(
            email="not_enrolled_visibility@example.com",
        )
        self.client.force_authenticate(user=student_user)

        response = self._detail(self.published)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
