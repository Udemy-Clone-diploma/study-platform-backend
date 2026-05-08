from django.contrib import admin as django_admin
from django.test import RequestFactory, TestCase

from apps.courses.admin import SoftDeleteAdminMixin
from apps.courses.models import Course, Lesson, Module

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


class AdminBulkDeleteRecomputesLessonsCountTests(TestCase):
    """``delete_queryset`` (the "Delete selected" admin action) must keep
    ``Course.lessons_count`` in sync.

    ``QuerySet.update(is_deleted=True)`` skips ``post_save``/``post_delete``,
    so the lessons_count signal never fires. ``ModuleAdmin`` and ``LessonAdmin``
    use ``LessonsCountRecomputeMixin`` to call the recompute explicitly after
    the bulk update.
    """

    @classmethod
    def setUpTestData(cls):
        _, cls.teacher_profile = make_teacher(email="bulk_admin@example.com")
        cls.course = make_course(
            cls.teacher_profile, title="Bulk", slug="bulk", short_description="x",
            full_description="x",
        )
        cls.module = Module.objects.create(course=cls.course, title="M", order=1)

    def setUp(self):
        Lesson.all_objects.filter(module=self.module).delete()
        for i in range(3):
            Lesson.objects.create(module=self.module, title=f"L{i}", order=i + 1)
        self.course.refresh_from_db()
        self.assertEqual(self.course.lessons_count, 3)

    def _admin(self, model):
        return django_admin.site._registry[model]

    def test_lesson_admin_bulk_delete_drops_count(self):
        request = RequestFactory().post("/admin/courses/lesson/")
        to_delete_ids = list(
            Lesson.objects.filter(module=self.module)
            .order_by("order")
            .values_list("pk", flat=True)
        )[:2]
        to_delete = Lesson.objects.filter(pk__in=to_delete_ids)

        self._admin(Lesson).delete_queryset(request, to_delete)

        self.course.refresh_from_db()
        self.assertEqual(self.course.lessons_count, 1)

    def test_module_admin_bulk_delete_drops_count_to_zero(self):
        request = RequestFactory().post("/admin/courses/module/")

        self._admin(Module).delete_queryset(
            request, Module.objects.filter(pk=self.module.pk)
        )

        self.course.refresh_from_db()
        self.assertEqual(self.course.lessons_count, 0)
