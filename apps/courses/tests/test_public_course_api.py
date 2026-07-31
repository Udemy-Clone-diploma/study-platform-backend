from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import (
    CohortMember,
    Course,
    CourseDeliveryFormat,
    PricingPlan,
)
from apps.curriculum.models import Lesson, LessonItem, Module, Question, Test
from apps.enrollments.models import Enrollment
from apps.enrollments.tests._factories import make_student
from apps.users.models import User

from ._factories import make_category, make_cohort, make_course, make_teacher


class PublicCourseApiContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        _, cls.teacher = make_teacher(
            email="public-contract-teacher@example.com",
            first_name="Public",
            last_name="Teacher",
        )
        cls.category = make_category(
            name="Public category",
            slug="public-category",
            featured_order=3,
        )
        cls.course = make_course(
            cls.teacher,
            title="Public contract",
            slug="public-contract",
            category=cls.category,
            status=Course.StatusChoices.PUBLISHED,
            moderator_comment="Internal note",
        )
        module = Module.objects.create(
            course=cls.course,
            title="Public module",
            order=1,
        )
        lesson = Lesson.objects.create(
            module=module,
            title="Public lesson summary",
            order=1,
            meeting_url="https://example.com/private-meeting",
            is_preview=False,
        )
        test = Test.objects.create(
            module=module,
            title="Private answer key",
            order=1,
        )
        Question.objects.create(
            test=test,
            question_type=Question.TypeChoices.SINGLE_CHOICE,
            text="Private question",
            options=["Wrong", "Correct"],
            correct_indices=[1],
            order=1,
        )
        LessonItem.objects.create(
            lesson=lesson,
            item_type=LessonItem.ItemType.TEXT,
            body_html="<p>Paid lesson body</p>",
            order=1,
        )
        delivery_format = CourseDeliveryFormat.objects.create(
            course=cls.course,
            format_type=CourseDeliveryFormat.FormatType.GROUP,
        )
        PricingPlan.objects.create(
            delivery_format=delivery_format,
            price="100.00",
            currency=PricingPlan.CurrencyChoices.USD,
        )
        cohort = make_cohort(
            cls.course,
            delivery_format=delivery_format,
            name="Public cohort",
        )
        _, student_profile = make_student(
            email="public-contract-student@example.com",
        )
        enrollment = Enrollment.objects.create(
            student_profile=student_profile,
            course=cls.course,
            delivery_format=delivery_format,
        )
        CohortMember.objects.create(cohort=cohort, enrollment=enrollment)

    def test_anonymous_public_detail_contains_only_public_contract(self):
        response = self.client.get(
            reverse("courses-public", args=[self.course.slug]),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            {
                "image_hash",
                "moderator_id",
                "status",
                "moderator_comment",
                "is_enrolled",
                "group_chat_url",
                "moderation_review",
            }.isdisjoint(response.data)
        )

        module = response.data["modules"][0]
        self.assertNotIn("tests", module)
        lesson = module["lessons"][0]
        self.assertTrue(
            {
                "min_score",
                "meeting_url",
                "is_manually_locked",
                "documents",
                "items",
                "tests",
                "source_lesson_id",
            }.isdisjoint(lesson)
        )

        delivery_format = response.data["delivery_formats"][0]
        self.assertTrue(
            {"chat_id", "completed_count"}.isdisjoint(delivery_format)
        )
        cohort = response.data["cohorts"][0]
        self.assertEqual(cohort["members_count"], 1)
        self.assertTrue({"chat_id", "members"}.isdisjoint(cohort))

    def test_anonymous_catalog_list_excludes_management_fields(self):
        response = self.client.get(reverse("courses-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        course = response.data["results"][0]
        self.assertTrue(
            {
                "status",
                "enrolled_at",
                "pending_edit_status",
                "moderator_id",
            }.isdisjoint(course)
        )

    def test_admin_catalog_list_keeps_management_fields(self):
        admin = User.objects.create_user(
            email="public-contract-admin@example.com",
            password="pass12345",
            role=User.RoleChoices.ADMINISTRATOR,
        )
        self.client.force_authenticate(user=admin)

        response = self.client.get(reverse("courses-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("status", response.data["results"][0])

    def test_public_category_list_excludes_featured_order(self):
        response = self.client.get(reverse("categories-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("featured_order", response.data["results"][0])
