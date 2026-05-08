from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Category, Course

from ._factories import make_category, make_course, make_teacher


class CoursePaginationTests(APITestCase):
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    @classmethod
    def setUpTestData(cls):
        _, cls.teacher_profile = make_teacher()
        cls.category = make_category(name="Development", slug="development")
        cls.other_category = make_category(name="Design", slug="design")

        for i in range(25):
            make_course(
                cls.teacher_profile,
                title=f"Dev Course {i:02d}",
                slug=f"dev-course-{i:02d}",
                category=cls.category,
                price=i,
            )
        for i in range(3):
            make_course(
                cls.teacher_profile,
                title=f"Design Course {i}",
                slug=f"design-course-{i}",
                category=cls.other_category,
            )

    def test_default_response_has_pagination_envelope(self):
        response = self.client.get(reverse("courses-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, response.data)
        self.assertEqual(response.data["count"], 28)
        self.assertEqual(len(response.data["results"]), self.DEFAULT_PAGE_SIZE)
        self.assertIsNone(response.data["previous"])
        self.assertIsNotNone(response.data["next"])

    def test_page_param_returns_next_page(self):
        response = self.client.get(reverse("courses-list"), {"page": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 8)
        self.assertIsNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])

    def test_page_size_query_param_overrides_default(self):
        response = self.client.get(reverse("courses-list"), {"page_size": 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 5)
        self.assertEqual(response.data["count"], 28)

    def test_page_size_capped_at_max(self):
        response = self.client.get(
            reverse("courses-list"), {"page_size": self.MAX_PAGE_SIZE + 50}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data["results"]), self.MAX_PAGE_SIZE)
        self.assertEqual(len(response.data["results"]), 28)

    def test_invalid_page_returns_404(self):
        response = self.client.get(reverse("courses-list"), {"page": 999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_pagination_composes_with_filter(self):
        response = self.client.get(
            reverse("courses-list"),
            {"category": "design", "page_size": 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)
        for course in response.data["results"]:
            self.assertTrue(course["slug"].startswith("design-course-"))

    def test_pagination_composes_with_ordering(self):
        response = self.client.get(
            reverse("courses-list"),
            {"category": "development", "ordering": "price", "page_size": 5},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prices = [c["price"] for c in response.data["results"]]
        self.assertEqual(prices, sorted(prices))
        self.assertEqual(len(prices), 5)

    def test_results_do_not_overlap_between_pages(self):
        first = self.client.get(reverse("courses-list"), {"page": 1, "page_size": 10})
        second = self.client.get(reverse("courses-list"), {"page": 2, "page_size": 10})

        first_ids = {c["id"] for c in first.data["results"]}
        second_ids = {c["id"] for c in second.data["results"]}
        self.assertEqual(first_ids & second_ids, set())


class CategoryPaginationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        for i in range(25):
            Category.objects.create(name=f"Category {i:02d}", slug=f"cat-{i:02d}")

    def test_categories_list_is_paginated(self):
        response = self.client.get(reverse("categories-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)

    def test_categories_list_respects_page_size(self):
        response = self.client.get(reverse("categories-list"), {"page_size": 7})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 7)
