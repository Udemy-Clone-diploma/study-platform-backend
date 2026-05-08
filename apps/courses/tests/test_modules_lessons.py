from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course, Lesson, Module

from ._factories import make_course, make_teacher


class ModuleLessonModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        _, cls.teacher_profile = make_teacher()
        cls.course = make_course(cls.teacher_profile, slug="m-l-course")

    def test_default_ordering_is_by_order(self):
        m2 = Module.objects.create(course=self.course, title="Two", order=2)
        m1 = Module.objects.create(course=self.course, title="One", order=1)

        modules = list(self.course.modules.all())

        self.assertEqual(modules, [m1, m2])

    def test_active_manager_hides_soft_deleted_modules(self):
        live = Module.objects.create(course=self.course, title="Live", order=1)
        Module.objects.create(
            course=self.course, title="Dead", order=2, is_deleted=True
        )

        ids = list(self.course.modules.values_list("id", flat=True))

        self.assertEqual(ids, [live.id])

    def test_unique_active_module_order_enforced(self):
        Module.objects.create(course=self.course, title="A", order=1)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Module.objects.create(course=self.course, title="B", order=1)

    def test_soft_deleted_module_does_not_block_new_one_at_same_order(self):
        Module.objects.create(
            course=self.course, title="Old", order=1, is_deleted=True
        )

        new_module = Module.objects.create(course=self.course, title="New", order=1)

        self.assertIsNotNone(new_module.pk)

    def test_unique_active_lesson_order_enforced(self):
        module = Module.objects.create(course=self.course, title="M", order=1)
        Lesson.objects.create(module=module, title="L1", order=1)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Lesson.objects.create(module=module, title="L2", order=1)


class LessonsCountSignalTests(TestCase):
    """Course.lessons_count is recomputed on Lesson and Module save/delete."""

    def setUp(self):
        _, self.teacher_profile = make_teacher()
        self.course = make_course(self.teacher_profile, slug="signal-course")
        self.module = Module.objects.create(
            course=self.course, title="M", order=1
        )

    def _refresh_count(self):
        self.course.refresh_from_db()
        return self.course.lessons_count

    def test_creating_lesson_increments_count(self):
        Lesson.objects.create(module=self.module, title="L1", order=1)
        Lesson.objects.create(module=self.module, title="L2", order=2)

        self.assertEqual(self._refresh_count(), 2)

    def test_soft_deleting_lesson_decrements_count(self):
        l1 = Lesson.objects.create(module=self.module, title="L1", order=1)
        Lesson.objects.create(module=self.module, title="L2", order=2)

        l1.is_deleted = True
        l1.save()

        self.assertEqual(self._refresh_count(), 1)

    def test_soft_deleting_module_drops_its_lessons_from_count(self):
        Lesson.objects.create(module=self.module, title="L1", order=1)
        Lesson.objects.create(module=self.module, title="L2", order=2)

        self.module.is_deleted = True
        self.module.save()

        self.assertEqual(self._refresh_count(), 0)

    def test_hard_deleting_lesson_decrements_count(self):
        lesson = Lesson.objects.create(module=self.module, title="L1", order=1)
        Lesson.objects.create(module=self.module, title="L2", order=2)

        lesson.delete()

        self.assertEqual(self._refresh_count(), 1)

    def test_hard_deleting_module_cascade_decrements_count(self):
        Lesson.objects.create(module=self.module, title="L1", order=1)
        Lesson.objects.create(module=self.module, title="L2", order=2)

        self.module.delete()

        self.assertEqual(self._refresh_count(), 0)


class CourseDetailIncludesModulesAndLessonsTests(APITestCase):
    """GET /courses/{slug}/ returns modules with nested non-deleted lessons in order."""

    @classmethod
    def setUpTestData(cls):
        _, cls.teacher_profile = make_teacher()
        cls.course = make_course(
            cls.teacher_profile,
            title="With Content",
            slug="with-content",
            status=Course.StatusChoices.PUBLISHED,
        )
        cls.module1 = Module.objects.create(
            course=cls.course, title="Intro", order=1, description="Intro module"
        )
        cls.module2 = Module.objects.create(
            course=cls.course, title="Advanced", order=2
        )
        cls.lesson1 = Lesson.objects.create(
            module=cls.module1, title="Hello", order=1, duration_minutes=10
        )
        cls.lesson2 = Lesson.objects.create(
            module=cls.module1, title="Setup", order=2, duration_minutes=15
        )
        Lesson.objects.create(
            module=cls.module1,
            title="Hidden",
            order=3,
            is_deleted=True,
        )
        Module.objects.create(
            course=cls.course, title="Hidden Module", order=99, is_deleted=True
        )

    def test_detail_includes_modules_in_order(self):
        response = self.client.get(reverse("courses-detail", args=[self.course.slug]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        modules = response.data["modules"]
        self.assertEqual([m["title"] for m in modules], ["Intro", "Advanced"])

    def test_detail_excludes_soft_deleted_modules(self):
        response = self.client.get(reverse("courses-detail", args=[self.course.slug]))

        titles = [m["title"] for m in response.data["modules"]]
        self.assertNotIn("Hidden Module", titles)

    def test_module_lessons_are_nested_and_excluded_when_deleted(self):
        response = self.client.get(reverse("courses-detail", args=[self.course.slug]))

        intro = next(m for m in response.data["modules"] if m["title"] == "Intro")
        titles = [l["title"] for l in intro["lessons"]]
        self.assertEqual(titles, ["Hello", "Setup"])

    def test_lesson_payload_includes_duration(self):
        response = self.client.get(reverse("courses-detail", args=[self.course.slug]))

        intro = next(m for m in response.data["modules"] if m["title"] == "Intro")
        durations = [l["duration_minutes"] for l in intro["lessons"]]
        self.assertEqual(durations, [10, 15])
