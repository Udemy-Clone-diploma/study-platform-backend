from django.contrib import admin as django_admin
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.courses.admin import SoftDeleteAdminMixin
from apps.courses.models import Category, Tag


class CategorySoftDeleteTests(TestCase):
    def test_active_manager_hides_soft_deleted(self):
        live = Category.objects.create(name="Live", slug="live")
        dead = Category.objects.create(name="Dead", slug="dead", is_deleted=True)

        slugs = list(Category.objects.values_list("slug", flat=True))

        self.assertIn(live.slug, slugs)
        self.assertNotIn(dead.slug, slugs)

    def test_all_objects_includes_soft_deleted(self):
        Category.objects.create(name="Live", slug="live")
        Category.objects.create(name="Dead", slug="dead", is_deleted=True)

        self.assertEqual(Category.all_objects.count(), 2)

    def test_admin_delete_flips_is_deleted_instead_of_dropping_row(self):
        category = Category.objects.create(name="To Soft Delete", slug="to-soft-delete")
        model_admin = django_admin.site._registry[Category]
        self.assertIsInstance(model_admin, SoftDeleteAdminMixin)

        request = RequestFactory().post("/admin/courses/category/")
        model_admin.delete_model(request, category)

        category.refresh_from_db()
        self.assertTrue(category.is_deleted)
        self.assertTrue(Category.all_objects.filter(pk=category.pk).exists())

    def test_admin_delete_queryset_marks_all_as_deleted(self):
        Category.objects.create(name="A", slug="cat-a")
        Category.objects.create(name="B", slug="cat-b")
        model_admin = django_admin.site._registry[Category]
        request = RequestFactory().post("/admin/courses/category/")

        model_admin.delete_queryset(request, Category.all_objects.all())

        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(Category.all_objects.count(), 2)


class TagSoftDeleteTests(TestCase):
    def test_active_manager_hides_soft_deleted(self):
        live = Tag.objects.create(name="Live")
        Tag.objects.create(name="Dead", is_deleted=True)

        names = list(Tag.objects.values_list("name", flat=True))

        self.assertIn(live.name, names)
        self.assertNotIn("Dead", names)

    def test_admin_uses_soft_delete_mixin(self):
        model_admin = django_admin.site._registry[Tag]
        self.assertIsInstance(model_admin, SoftDeleteAdminMixin)

    def test_admin_delete_flips_is_deleted(self):
        tag = Tag.objects.create(name="Doomed")
        model_admin = django_admin.site._registry[Tag]
        request = RequestFactory().post("/admin/courses/tag/")

        model_admin.delete_model(request, tag)

        tag.refresh_from_db()
        self.assertTrue(tag.is_deleted)


class FeaturedCategoriesHidesDeletedTests(APITestCase):
    """The featured (top-N) categories endpoint must skip soft-deleted ones."""

    def test_deleted_category_not_in_featured(self):
        live = Category.objects.create(name="Live", slug="live")
        Category.objects.create(name="Dead", slug="dead", is_deleted=True)

        response = self.client.get(reverse("categories-featured"))

        slugs = [c["slug"] for c in response.data]
        self.assertIn(live.slug, slugs)
        self.assertNotIn("dead", slugs)
