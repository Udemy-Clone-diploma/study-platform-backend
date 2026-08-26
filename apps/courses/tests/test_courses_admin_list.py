from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.users.models import User

from ._factories import make_course, make_teacher


class AdminCourseListStatusTests(APITestCase):
    """GET /courses/ returns all statuses for admins and honors the admin-only
    ?status= filter; every other caller stays on the published-only catalog."""

    @classmethod
    def setUpTestData(cls):
        _, cls.teacher = make_teacher()
        cls.published = make_course(
            cls.teacher,
            title="Published",
            slug="published",
            status=Course.StatusChoices.PUBLISHED,
        )
        cls.draft = make_course(
            cls.teacher,
            title="Draft",
            slug="draft",
            status=Course.StatusChoices.DRAFT,
        )
        cls.review = make_course(
            cls.teacher,
            title="Review",
            slug="review",
            status=Course.StatusChoices.REVIEW,
        )
        # DELETE archives via soft delete (status=archived + is_deleted=True),
        # so this row is only reachable through Course.all_objects.
        cls.archived = make_course(
            cls.teacher,
            title="Archived",
            slug="archived",
            status=Course.StatusChoices.ARCHIVED,
            is_deleted=True,
        )
        # Internal shadow draft of a published course; must never surface.
        cls.pending_edit = make_course(
            cls.teacher,
            title="Pending Edit",
            slug="pending-edit",
            status=Course.StatusChoices.PENDING_EDIT,
        )
        cls.url = reverse("courses-list")

    def _slugs(self, response):
        return {row["slug"] for row in response.data["results"]}

    def _authenticate_admin(self):
        admin = User.objects.create_user(
            email="admin@example.com",
            password="pass12345",
            role="administrator",
        )
        self.client.force_authenticate(user=admin)

    def test_admin_list_includes_all_statuses_except_pending_edit(self):
        self._authenticate_admin()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._slugs(response), {"published", "draft", "review", "archived"})

    def test_admin_status_filter_narrows_to_selected(self):
        self._authenticate_admin()

        response = self.client.get(self.url, {"status": "draft,review"})

        self.assertEqual(self._slugs(response), {"draft", "review"})

    def test_admin_status_filter_reaches_soft_deleted_archived(self):
        self._authenticate_admin()

        response = self.client.get(self.url, {"status": "archived"})

        self.assertEqual(self._slugs(response), {"archived"})

    def test_admin_status_filter_drops_unknown_values(self):
        self._authenticate_admin()

        response = self.client.get(self.url, {"status": "draft,bogus"})

        self.assertEqual(self._slugs(response), {"draft"})

    def test_admin_all_invalid_statuses_fall_back_to_full_list(self):
        self._authenticate_admin()

        response = self.client.get(self.url, {"status": "bogus"})

        self.assertEqual(self._slugs(response), {"published", "draft", "review", "archived"})

    def test_admin_cannot_surface_pending_edit_via_filter(self):
        self._authenticate_admin()

        response = self.client.get(self.url, {"status": "pending_edit"})

        self.assertNotIn("pending-edit", self._slugs(response))

    def test_anonymous_status_filter_ignored_stays_published_only(self):
        response = self.client.get(self.url, {"status": "draft,review"})

        self.assertEqual(self._slugs(response), {"published"})

    def test_student_status_filter_ignored_stays_published_only(self):
        student = User.objects.create_user(
            email="student@example.com",
            password="pass12345",
            role="student",
        )
        self.client.force_authenticate(user=student)

        response = self.client.get(self.url, {"status": "draft,review"})

        self.assertEqual(self._slugs(response), {"published"})
