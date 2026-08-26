from io import StringIO
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.courses.management.commands.teacher_demo_catalog import COURSES, REVISION_COMMENT
from apps.courses.models import Cohort, Course, CourseDeliveryFormat, PricingPlan
from apps.curriculum.models import Lesson, LessonDocument, LessonItem, Module, Question, Test
from apps.schedule.models import CohortSchedule, ScheduleSlot
from apps.users.models import User

from ._factories import make_course, make_teacher


class SeedTeacherDemoCoursesCommandTests(TestCase):
    def setUp(self):
        self.teacher_user, self.teacher = make_teacher(
            email="jared.kachinski@example.com",
            first_name="Jared",
            last_name="Kachinski",
        )
        _, other_teacher = make_teacher(email="other-teacher@example.com")
        self.unrelated = make_course(
            other_teacher,
            title="Existing Unrelated Course",
            slug="existing-unrelated-course",
        )
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)

    def _run(self):
        with override_settings(DEBUG=True, MEDIA_ROOT=self.media.name):
            call_command(
                "seed_teacher_demo_courses",
                "--teacher-email",
                self.teacher_user.email,
                stdout=StringIO(),
            )

    def test_creates_realistic_catalog_without_touching_unrelated_course(self):
        self._run()

        courses = Course.objects.filter(
            teacher_profile=self.teacher,
            slug__in={spec["slug"] for spec in COURSES},
        )
        self.assertEqual(courses.count(), 6)
        self.assertEqual(
            set(courses.values_list("status", flat=True)),
            {"published", "review", "draft", "needs_revision"},
        )
        self.assertEqual(Module.objects.filter(course__in=courses).count(), 33)
        self.assertEqual(Lesson.objects.filter(module__course__in=courses).count(), 69)
        self.assertTrue(LessonItem.objects.filter(lesson__module__course__in=courses, item_type="text").exists())
        self.assertTrue(LessonItem.objects.filter(lesson__module__course__in=courses, item_type="video").exists())
        self.assertTrue(LessonItem.objects.filter(lesson__module__course__in=courses, item_type="test").exists())
        self.assertTrue(LessonDocument.objects.filter(lesson__module__course__in=courses).exists())
        self.assertEqual(
            set(Question.objects.filter(test__module__course__in=courses).values_list("question_type", flat=True)),
            {"single_choice", "multiple_choice", "true_false", "short_answer"},
        )

        fundamentals = courses.get(slug="demo-qa-software-testing-fundamentals")
        self.assertTrue(fundamentals.with_certificate)
        self.assertEqual(fundamentals.created_at.date().isoformat(), "2025-11-18")
        self.assertEqual(
            fundamentals.delivery_formats.get(format_type="self_paced").pricing.installment_count,
            3,
        )

        manual = courses.get(slug="demo-qa-manual-qa-job-ready")
        cohort = Cohort.objects.get(course=manual, name="Manual QA — September 2026")
        self.assertEqual(cohort.group_size, 12)
        self.assertEqual(CohortSchedule.objects.filter(cohort=cohort).count(), 2)

        automation = courses.get(slug="demo-qa-python-selenium-automation")
        self.assertEqual(automation.delivery_formats.count(), 2)
        self.assertEqual(
            ScheduleSlot.objects.filter(
                delivery_format__course=automation,
                delivery_format__format_type="individual",
            ).count(),
            3,
        )

        revision = courses.get(slug="demo-qa-interview-preparation")
        self.assertEqual(revision.moderator_comment, REVISION_COMMENT)
        self.assertEqual(revision.moderation_review.final_comment, REVISION_COMMENT)

        self.unrelated.refresh_from_db()
        self.assertEqual(self.unrelated.title, "Existing Unrelated Course")

    def test_second_run_is_idempotent(self):
        self._run()
        counts = self._demo_counts()

        self._run()

        self.assertEqual(self._demo_counts(), counts)

    def _demo_counts(self):
        course_ids = Course.objects.filter(
            teacher_profile=self.teacher,
            slug__startswith="demo-qa-",
        ).values_list("id", flat=True)
        return {
            "courses": Course.objects.filter(id__in=course_ids).count(),
            "formats": CourseDeliveryFormat.objects.filter(course_id__in=course_ids).count(),
            "pricing": PricingPlan.objects.filter(delivery_format__course_id__in=course_ids).count(),
            "cohorts": Cohort.objects.filter(course_id__in=course_ids).count(),
            "modules": Module.objects.filter(course_id__in=course_ids).count(),
            "lessons": Lesson.objects.filter(module__course_id__in=course_ids).count(),
            "items": LessonItem.objects.filter(lesson__module__course_id__in=course_ids).count(),
            "documents": LessonDocument.objects.filter(lesson__module__course_id__in=course_ids).count(),
            "tests": Test.objects.filter(module__course_id__in=course_ids).count(),
            "questions": Question.objects.filter(test__module__course_id__in=course_ids).count(),
            "cohort_schedules": CohortSchedule.objects.filter(cohort__course_id__in=course_ids).count(),
            "slots": ScheduleSlot.objects.filter(delivery_format__course_id__in=course_ids).count(),
        }

    @override_settings(DEBUG=False)
    def test_refuses_to_run_outside_debug_without_force(self):
        with self.assertRaisesMessage(CommandError, "disabled while DEBUG is false"):
            call_command(
                "seed_teacher_demo_courses",
                "--teacher-email",
                self.teacher_user.email,
                stdout=StringIO(),
            )

    @override_settings(DEBUG=True)
    def test_requires_existing_teacher(self):
        student = User.objects.create_user(
            email="not-a-teacher@example.com",
            password="pass12345",
            role=User.RoleChoices.STUDENT,
        )
        with self.assertRaisesMessage(CommandError, "is not a teacher"):
            call_command(
                "seed_teacher_demo_courses",
                "--teacher-email",
                student.email,
                stdout=StringIO(),
            )
