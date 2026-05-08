from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course

from ._factories import make_category, make_course, make_teacher


class CourseDetailTeacherInfoTests(APITestCase):
    """The detail endpoint must include the teacher payload (id, name, avatar, bio)."""

    @classmethod
    def setUpTestData(cls):
        _, cls.teacher_profile = make_teacher(
            email="famous@example.com",
            first_name="Ada",
            last_name="Lovelace",
        )
        cls.teacher_profile.bio = "Computing pioneer."
        cls.teacher_profile.save(update_fields=["bio"])
        cls.category = make_category()
        cls.course = make_course(
            cls.teacher_profile,
            title="Algorithms",
            slug="algorithms",
            category=cls.category,
            status=Course.StatusChoices.PUBLISHED,
        )

    def test_detail_includes_teacher_payload(self):
        response = self.client.get(reverse("courses-detail", args=[self.course.slug]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        teacher = response.data["teacher"]
        self.assertEqual(teacher["id"], self.teacher_profile.pk)
        self.assertEqual(teacher["name"], "Ada Lovelace")
        self.assertEqual(teacher["bio"], "Computing pioneer.")
        self.assertIn("avatar", teacher)

    def test_detail_includes_category_payload(self):
        response = self.client.get(reverse("courses-detail", args=[self.course.slug]))

        self.assertEqual(response.data["category"]["slug"], self.category.slug)

    def test_detail_returns_image_url_or_none(self):
        response = self.client.get(reverse("courses-detail", args=[self.course.slug]))

        # image is a SerializerMethodField; with no upload it should be None.
        self.assertIsNone(response.data["image"])
