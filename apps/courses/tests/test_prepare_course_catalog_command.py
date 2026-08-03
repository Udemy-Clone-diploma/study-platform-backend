from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.courses.management.commands.prepare_course_catalog import COURSE_SPECS, REVIEW_SPECS
from apps.courses.models import Course, PricingPlan
from apps.curriculum.models import Lesson, Module
from apps.enrollments.models import Enrollment
from apps.reviews.models import Review
from apps.users.models import User

from ._factories import make_course, make_teacher


class PrepareCourseCatalogCommandTests(TestCase):
    def setUp(self):
        _, jordan = make_teacher(
            email="jordan@example.com",
            first_name="Jordan",
            last_name="Peterson",
        )
        self.legacy_course = make_course(
            jordan,
            title="Legacy course",
            slug="legacy-course",
        )
        self.legacy_course.delivery_formats.all().delete()
        Course.all_objects.filter(pk=self.legacy_course.pk).update(
            category=None,
            published_at=None,
            short_description="Short",
            full_description="Full",
        )

    def test_repairs_legacy_courses_and_creates_demo_catalog_idempotently(self):
        output = StringIO()

        call_command("prepare_course_catalog", stdout=output)

        self.legacy_course.refresh_from_db()
        self.assertIsNotNone(self.legacy_course.category_id)
        self.assertIsNotNone(self.legacy_course.published_at)
        self.assertGreaterEqual(len(self.legacy_course.short_description), 20)
        self.assertGreaterEqual(len(self.legacy_course.full_description), 50)
        self.assertEqual(self.legacy_course.modules.count(), 2)
        self.assertEqual(
            Lesson.objects.filter(module__course=self.legacy_course).count(),
            4,
        )

        legacy_format = self.legacy_course.delivery_formats.get(
            format_type=self.legacy_course.delivery_type,
        )
        self.assertTrue(PricingPlan.objects.filter(delivery_format=legacy_format).exists())

        demo_slugs = {spec["slug"] for spec in COURSE_SPECS}
        demo_courses = Course.objects.filter(slug__in=demo_slugs)
        self.assertEqual(demo_courses.count(), 9)
        self.assertEqual(
            User.objects.filter(
                email__in={
                    "jordan@example.com",
                    "sophia.martinez@example.com",
                    "liam.anderson@example.com",
                },
                role=User.RoleChoices.TEACHER,
            ).count(),
            3,
        )

        for course in demo_courses:
            self.assertEqual(course.status, Course.StatusChoices.PUBLISHED)
            self.assertIsNotNone(course.category_id)
            self.assertTrue(course.delivery_formats.exists())
            self.assertEqual(
                PricingPlan.objects.filter(
                    delivery_format__course=course,
                ).count(),
                course.delivery_formats.count(),
            )
            self.assertEqual(Module.objects.filter(course=course).count(), 2)
            self.assertEqual(Lesson.objects.filter(module__course=course).count(), 4)

        expected_review_count = sum(len(specs) for specs in REVIEW_SPECS.values())
        self.assertEqual(Review.objects.count(), expected_review_count)
        self.assertEqual(
            Review.objects.filter(course__slug="ux-research-fundamentals").count(),
            5,
        )
        self.assertEqual(Enrollment.objects.count(), expected_review_count)

        counts_after_first_run = {
            "users": User.all_objects.count(),
            "courses": Course.all_objects.count(),
            "formats": sum(course.delivery_formats.count() for course in Course.objects.all()),
            "pricing": PricingPlan.objects.count(),
            "modules": Module.all_objects.count(),
            "lessons": Lesson.all_objects.count(),
            "enrollments": Enrollment.all_objects.count(),
            "reviews": Review.all_objects.count(),
        }

        call_command("prepare_course_catalog", stdout=StringIO())

        counts_after_second_run = {
            "users": User.all_objects.count(),
            "courses": Course.all_objects.count(),
            "formats": sum(course.delivery_formats.count() for course in Course.objects.all()),
            "pricing": PricingPlan.objects.count(),
            "modules": Module.all_objects.count(),
            "lessons": Lesson.all_objects.count(),
            "enrollments": Enrollment.all_objects.count(),
            "reviews": Review.all_objects.count(),
        }
        self.assertEqual(counts_after_second_run, counts_after_first_run)

        call_command("prepare_course_catalog", "--check-only", stdout=StringIO())
        self.assertIn("Catalog prepared", output.getvalue())

    def test_check_only_reports_broken_catalog_without_mutating_it(self):
        broken_course_id = self.legacy_course.pk

        with self.assertRaisesMessage(CommandError, "Catalog check failed"):
            call_command("prepare_course_catalog", "--check-only", stdout=StringIO())

        course = Course.all_objects.get(pk=broken_course_id)
        self.assertIsNone(course.category_id)
        self.assertFalse(course.delivery_formats.exists())
