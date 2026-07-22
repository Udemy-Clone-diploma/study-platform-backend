from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Category
from apps.users.models import User

from ._factories import make_course, make_teacher


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


class CategoryWritePermissionTests(APITestCase):
    """Only administrators may create, update, or delete categories."""

    def setUp(self):
        self.category = Category.objects.create(name="Development", slug="development")

    def test_anonymous_cannot_create(self):
        response = self.client.post(
            reverse("categories-list"), {"name": "New"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_cannot_create(self):
        student = User.objects.create_user(
            email="student@example.com", password="pass12345", role="student"
        )
        self.client.force_authenticate(user=student)

        response = self.client.post(
            reverse("categories-list"), {"name": "New"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_moderator_cannot_update(self):
        moderator = User.objects.create_user(
            email="moderator@example.com", password="pass12345", role="moderator"
        )
        self.client.force_authenticate(user=moderator)

        response = self.client.patch(
            reverse("categories-detail", args=[self.category.pk]),
            {"name": "Renamed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_delete(self):
        student = User.objects.create_user(
            email="student2@example.com", password="pass12345", role="student"
        )
        self.client.force_authenticate(user=student)

        response = self.client.delete(
            reverse("categories-detail", args=[self.category.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CategoryCreateTests(APITestCase):
    def setUp(self):
        admin = User.objects.create_user(
            email="admin@example.com", password="pass12345", role="administrator"
        )
        self.client.force_authenticate(user=admin)

    def test_create_with_explicit_slug(self):
        response = self.client.post(
            reverse("categories-list"),
            {"name": "Data Science", "slug": "data-sci"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["slug"], "data-sci")
        self.assertEqual(response.data["courses_count"], 0)

    def test_slug_auto_generated_from_name_when_omitted(self):
        response = self.client.post(
            reverse("categories-list"),
            {"name": "Machine Learning"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["slug"], "machine-learning")

    def test_duplicate_name_rejected_case_insensitive(self):
        Category.objects.create(name="Design", slug="design")

        response = self.client.post(
            reverse("categories-list"), {"name": "design"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_explicit_slug_colliding_with_soft_deleted_rejected(self):
        Category.objects.create(name="Retired", slug="taken", is_deleted=True)

        response = self.client.post(
            reverse("categories-list"),
            {"name": "Fresh", "slug": "taken"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_auto_slug_suffixes_past_soft_deleted_collision(self):
        Category.objects.create(name="Retired", slug="gaming", is_deleted=True)

        response = self.client.post(
            reverse("categories-list"), {"name": "Gaming"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["slug"], "gaming-2")


class CategoryUpdateTests(APITestCase):
    def setUp(self):
        admin = User.objects.create_user(
            email="admin@example.com", password="pass12345", role="administrator"
        )
        self.client.force_authenticate(user=admin)
        self.category = Category.objects.create(name="Development", slug="development")

    def test_patch_sets_featured_order(self):
        response = self.client.patch(
            reverse("categories-detail", args=[self.category.pk]),
            {"featured_order": 5},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["featured_order"], 5)
        self.category.refresh_from_db()
        self.assertEqual(self.category.featured_order, 5)

    def test_patch_duplicate_name_rejected(self):
        Category.objects.create(name="Design", slug="design")

        response = self.client.patch(
            reverse("categories-detail", args=[self.category.pk]),
            {"name": "Design"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_keeping_own_name_allowed(self):
        response = self.client.patch(
            reverse("categories-detail", args=[self.category.pk]),
            {"name": "Development", "description": "Updated"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["description"], "Updated")


class CategoryDeleteTests(APITestCase):
    def setUp(self):
        admin = User.objects.create_user(
            email="admin@example.com", password="pass12345", role="administrator"
        )
        self.client.force_authenticate(user=admin)
        _, self.teacher_profile = make_teacher()

    def test_delete_empty_category_soft_deletes(self):
        category = Category.objects.create(name="Empty", slug="empty")

        response = self.client.delete(
            reverse("categories-detail", args=[category.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(pk=category.pk).exists())
        self.assertTrue(Category.all_objects.get(pk=category.pk).is_deleted)

    def test_delete_category_with_active_course_returns_409(self):
        category = Category.objects.create(name="Busy", slug="busy")
        make_course(self.teacher_profile, category=category)

        response = self.client.delete(
            reverse("categories-detail", args=[category.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        category.refresh_from_db()
        self.assertFalse(category.is_deleted)

    def test_soft_deleted_course_does_not_block_delete(self):
        category = Category.objects.create(name="Stale", slug="stale")
        course = make_course(self.teacher_profile, category=category)
        course.is_deleted = True
        course.save(update_fields=["is_deleted"])

        response = self.client.delete(
            reverse("categories-detail", args=[category.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
