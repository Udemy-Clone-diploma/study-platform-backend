from django.contrib import admin as django_admin
from django.test import RequestFactory, TestCase

from apps.courses.admin import SoftDeleteAdminMixin
from apps.courses.models import Course

from ._factories import make_course, make_teacher


class CourseAdminSoftDeleteTests(TestCase):
    """CourseAdmin must soft-delete instead of issuing SQL DELETE.

    Regression: PR #27 (Module + Lesson) rewrote CourseAdmin and dropped
    SoftDeleteAdminMixin, so admin "Delete" was hard-deleting Course rows.
    """

    @classmethod
    def setUpTestData(cls):
        _, cls.teacher_profile = make_teacher(email="course_admin_teacher@example.com")
        cls.course = make_course(
            cls.teacher_profile,
            title="Soft Delete Me",
            slug="soft-delete-me",
            short_description="x",
            full_description="x",
            duration_hours=1,
            status=Course.StatusChoices.DRAFT,
        )

    def _course_admin(self):
        model_admin = django_admin.site._registry[Course]
        self.assertIsInstance(model_admin, SoftDeleteAdminMixin)
        return model_admin

    def test_delete_model_flips_is_deleted_and_keeps_row(self):
        model_admin = self._course_admin()
        request = RequestFactory().post("/admin/courses/course/")

        model_admin.delete_model(request, self.course)

        self.course.refresh_from_db()
        self.assertTrue(self.course.is_deleted)
        self.assertTrue(Course.all_objects.filter(pk=self.course.pk).exists())
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())

    def test_admin_changelist_includes_soft_deleted_rows(self):
        Course.all_objects.filter(pk=self.course.pk).update(is_deleted=True)
        model_admin = self._course_admin()
        request = RequestFactory().get("/admin/courses/course/")

        queryset = model_admin.get_queryset(request)

        self.assertIn(self.course, queryset)
