from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course

from ._factories import make_category, make_course, make_teacher


class CourseFilterTests(APITestCase):
    def setUp(self):
        _, self.teacher_profile = make_teacher()
        self.category_dev = make_category(name="Development", slug="development")
        self.category_design = make_category(name="Design", slug="design")

        self.course_dev = make_course(
            self.teacher_profile,
            title="Django Course",
            slug="django-course",
            category=self.category_dev,
        )
        self.course_design = make_course(
            self.teacher_profile,
            title="Figma Course",
            slug="figma-course",
            category=self.category_design,
        )
        self.course_no_category = make_course(
            self.teacher_profile,
            title="No Category Course",
            slug="no-category-course",
            category=None,
        )

    def test_filter_by_category_slug_returns_matching_courses(self):
        response = self.client.get(reverse("courses-list"), {"category": "development"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "django-course")

    def test_filter_by_category_slug_excludes_other_categories(self):
        response = self.client.get(reverse("courses-list"), {"category": "design"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [c["slug"] for c in response.data["results"]]
        self.assertIn("figma-course", slugs)
        self.assertNotIn("django-course", slugs)

    def test_filter_by_nonexistent_slug_returns_empty_list(self):
        response = self.client.get(
            reverse("courses-list"), {"category": "nonexistent-category"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_search_returns_courses_matching_title(self):
        response = self.client.get(reverse("courses-list"), {"search": "django"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [c["slug"] for c in response.data["results"]]
        self.assertEqual(slugs, ["django-course"])

    def test_search_returns_courses_matching_category(self):
        response = self.client.get(reverse("courses-list"), {"search": "design"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [c["slug"] for c in response.data["results"]]
        self.assertIn("figma-course", slugs)
        self.assertNotIn("django-course", slugs)

    def test_search_can_be_combined_with_category_filter(self):
        response = self.client.get(
            reverse("courses-list"),
            {"category": "development", "search": "figma"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_no_filter_returns_all_courses(self):
        response = self.client.get(reverse("courses-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 3)

    def test_filter_by_level(self):
        Course.all_objects.filter(slug="django-course").update(
            level=Course.LevelChoices.ADVANCED
        )

        response = self.client.get(reverse("courses-list"), {"level": "advanced"})

        slugs = [c["slug"] for c in response.data["results"]]
        self.assertEqual(slugs, ["django-course"])

    def test_filter_by_pricing_type_in(self):
        Course.all_objects.filter(slug="figma-course").update(
            pricing_type=Course.PricingTypeChoices.FULL_PAYMENT, price="50.00"
        )

        response = self.client.get(
            reverse("courses-list"), {"pricing_type": "full_payment"}
        )

        slugs = [c["slug"] for c in response.data["results"]]
        self.assertEqual(slugs, ["figma-course"])

    def test_filter_with_certificate_boolean(self):
        Course.all_objects.filter(slug="django-course").update(with_certificate=True)

        response = self.client.get(
            reverse("courses-list"), {"with_certificate": "true"}
        )

        slugs = [c["slug"] for c in response.data["results"]]
        self.assertEqual(slugs, ["django-course"])

    def test_filter_rating_min(self):
        Course.all_objects.filter(slug="django-course").update(rating_avg="4.5")
        Course.all_objects.filter(slug="figma-course").update(rating_avg="3.5")

        response = self.client.get(reverse("courses-list"), {"rating_min": "4.0"})

        slugs = [c["slug"] for c in response.data["results"]]
        self.assertEqual(slugs, ["django-course"])

    def test_ordering_by_price_ascending(self):
        Course.all_objects.filter(slug="django-course").update(price="20.00")
        Course.all_objects.filter(slug="figma-course").update(price="10.00")
        Course.all_objects.filter(slug="no-category-course").update(price="30.00")

        response = self.client.get(reverse("courses-list"), {"ordering": "price"})

        slugs = [c["slug"] for c in response.data["results"]]
        self.assertEqual(
            slugs, ["figma-course", "django-course", "no-category-course"]
        )

    def test_default_ordering_is_created_at_desc(self):
        response = self.client.get(reverse("courses-list"))

        # Last created should appear first.
        slugs = [c["slug"] for c in response.data["results"]]
        self.assertEqual(slugs[0], "no-category-course")
