from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Category, Course

from ._factories import make_course, make_teacher


class TopNEndpointsAreNotPaginatedTests(APITestCase):
    """The home-page top-N endpoints return a raw list, not the paginated envelope."""

    @classmethod
    def setUpTestData(cls):
        _, cls.teacher_profile = make_teacher()
        Category.objects.create(name="A", slug="a")

    def test_new_courses_endpoint_returns_list(self):
        response = self.client.get(reverse("new-courses"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_popular_courses_endpoint_returns_list(self):
        response = self.client.get(reverse("popular-courses"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_featured_categories_endpoint_returns_list(self):
        response = self.client.get(reverse("categories-featured"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


class TopNLimitParamTests(APITestCase):
    """The top-N endpoints accept ?limit=N (capped at MAX_TOP_N_LIMIT)."""

    DEFAULT_NEW = 8
    DEFAULT_POPULAR = 8
    DEFAULT_FEATURED = 6
    MAX_LIMIT = 50

    @classmethod
    def setUpTestData(cls):
        _, cls.teacher_profile = make_teacher()

        for i in range(60):
            make_course(
                cls.teacher_profile,
                title=f"Top-N Course {i:02d}",
                slug=f"top-n-course-{i:02d}",
                status=Course.StatusChoices.PUBLISHED,
            )
        for i in range(15):
            Category.objects.create(name=f"Cat {i:02d}", slug=f"cat-{i:02d}")

    def test_new_courses_default_limit(self):
        response = self.client.get(reverse("new-courses"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), self.DEFAULT_NEW)

    def test_new_courses_explicit_limit(self):
        response = self.client.get(reverse("new-courses"), {"limit": 3})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_new_courses_limit_capped_at_max(self):
        response = self.client.get(reverse("new-courses"), {"limit": 999})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), self.MAX_LIMIT)

    def test_popular_courses_explicit_limit(self):
        response = self.client.get(reverse("popular-courses"), {"limit": 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 5)

    def test_featured_categories_default_limit(self):
        response = self.client.get(reverse("categories-featured"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), self.DEFAULT_FEATURED)

    def test_featured_categories_explicit_limit(self):
        response = self.client.get(reverse("categories-featured"), {"limit": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 10)

    def test_invalid_limit_returns_400(self):
        for bad_value in ("abc", "0", "-3", "1.5"):
            with self.subTest(value=bad_value):
                response = self.client.get(
                    reverse("new-courses"), {"limit": bad_value}
                )
                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST
                )
                self.assertIn("limit", response.data)


class TopNExcludesNonPublishedAndDeletedTests(APITestCase):
    """new/popular endpoints must show only PUBLISHED, not-deleted courses."""

    @classmethod
    def setUpTestData(cls):
        _, cls.teacher_profile = make_teacher()
        cls.published = make_course(
            cls.teacher_profile,
            title="Published",
            slug="published",
            status=Course.StatusChoices.PUBLISHED,
        )
        make_course(
            cls.teacher_profile,
            title="Draft",
            slug="draft",
            status=Course.StatusChoices.DRAFT,
        )
        make_course(
            cls.teacher_profile,
            title="Soft Deleted",
            slug="soft-deleted",
            status=Course.StatusChoices.PUBLISHED,
            is_deleted=True,
        )

    def test_new_courses_excludes_drafts_and_deleted(self):
        response = self.client.get(reverse("new-courses"))

        slugs = [c["slug"] for c in response.data]
        self.assertEqual(slugs, ["published"])

    def test_popular_courses_excludes_drafts_and_deleted(self):
        response = self.client.get(reverse("popular-courses"))

        slugs = [c["slug"] for c in response.data]
        self.assertEqual(slugs, ["published"])


class FeaturedCategoriesUrlTests(APITestCase):
    """The home-page categories endpoint moved from /courses/categories/ to /categories/featured/."""

    def test_old_url_no_longer_returns_featured_list(self):
        response = self.client.get("/api/v1/courses/categories/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_new_url_works(self):
        response = self.client.get(reverse("categories-featured"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
