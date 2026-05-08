from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Category


class CategoryViewSetTests(APITestCase):
    def setUp(self):
        self.category_dev = Category.objects.create(
            name="Development",
            slug="development",
            description="Programming courses",
        )
        self.category_design = Category.objects.create(
            name="Design",
            slug="design",
            description="Design courses",
        )

    def test_list_returns_all_categories(self):
        response = self.client.get(reverse("categories-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_list_returns_correct_fields(self):
        response = self.client.get(reverse("categories-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        category = response.data["results"][0]
        self.assertIn("id", category)
        self.assertIn("name", category)
        self.assertIn("slug", category)
        self.assertIn("description", category)

    def test_soft_deleted_categories_hidden_from_list(self):
        Category.objects.filter(slug="design").update(is_deleted=True)

        response = self.client.get(reverse("categories-list"))

        slugs = [c["slug"] for c in response.data["results"]]
        self.assertEqual(slugs, ["development"])
