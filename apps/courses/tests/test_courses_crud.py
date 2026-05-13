from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course, Tag
from apps.users.models import ModeratorProfile, User

from ._factories import make_category, make_course, make_teacher


class CourseViewSetTests(APITestCase):
    def setUp(self):
        teacher_user, self.teacher_profile = make_teacher()
        moderator_user = User.objects.create_user(
            email="moderator@example.com",
            password="pass12345",
            role="moderator",
        )
        self.moderator_profile = ModeratorProfile.objects.create(
            user=moderator_user,
            level="senior",
        )
        self.client.force_authenticate(user=teacher_user)
        self.category = make_category(description="Programming courses")
        self.tag = Tag.objects.create(name="Python")
        self.course = make_course(
            self.teacher_profile,
            title="Backend Engineering",
            slug="backend-engineering",
            short_description="Learn APIs",
            full_description="A deep dive into backend development.",
            moderator_profile=self.moderator_profile,
            category=self.category,
            duration_hours=12,
            lessons_count=6,
            status=Course.StatusChoices.DRAFT,
        )
        self.course.tags.add(self.tag)

    def test_list_uses_list_serializer(self):
        self.course.status = Course.StatusChoices.PUBLISHED
        self.course.save(update_fields=["status"])

        response = self.client.get(reverse("courses-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"]
        self.assertEqual(results[0]["slug"], self.course.slug)
        self.assertNotIn("full_description", results[0])
        self.assertEqual(results[0]["teacher_name"], "")

    def test_retrieve_uses_detail_serializer(self):
        response = self.client.get(reverse("courses-detail", args=[self.course.slug]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_description"], self.course.full_description)
        self.assertEqual(response.data["teacher"]["id"], self.teacher_profile.pk)
        self.assertEqual(response.data["moderator_id"], self.moderator_profile.pk)

    def test_create_course(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Advanced Django",
                "short_description": "Build production APIs",
                "full_description": "Advanced patterns for Django and DRF.",
                "teacher_profile": self.teacher_profile.pk,
                "moderator_profile": self.moderator_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.ADVANCED,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.WITH_TEACHER,
                "delivery_type": Course.DeliveryTypeChoices.GROUP,
                "course_type": Course.CourseTypeChoices.PROFESSION,
                "pricing_type": Course.PricingTypeChoices.FULL_PAYMENT,
                "price": "199.99",
                "duration_hours": 24,
                "lessons_count": 10,
                "with_certificate": True,
                "is_on_sale": False,
                "status": Course.StatusChoices.REVIEW,
                "tag_ids": [self.tag.pk],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["full_description"],
            "Advanced patterns for Django and DRF.",
        )
        self.assertEqual(response.data["slug"], "advanced-django")
        self.assertEqual(response.data["category"]["id"], self.category.pk)
        self.assertEqual(response.data["tags"][0]["id"], self.tag.pk)

    def test_create_course_ignores_provided_slug(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Advanced Django",
                "short_description": "Build production APIs",
                "full_description": "Advanced patterns for Django and DRF.",
                "slug": "teacher-custom-slug",
                "teacher_profile": self.teacher_profile.pk,
                "moderator_profile": self.moderator_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.ADVANCED,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.WITH_TEACHER,
                "delivery_type": Course.DeliveryTypeChoices.GROUP,
                "course_type": Course.CourseTypeChoices.PROFESSION,
                "pricing_type": Course.PricingTypeChoices.FULL_PAYMENT,
                "price": "199.99",
                "duration_hours": 24,
                "lessons_count": 10,
                "with_certificate": True,
                "is_on_sale": False,
                "status": Course.StatusChoices.REVIEW,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["slug"], "advanced-django")

    def test_create_course_generates_unique_slug_when_title_repeats(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": self.course.title,
                "short_description": "Another course with the same title",
                "full_description": "Same title, different course.",
                "teacher_profile": self.teacher_profile.pk,
                "moderator_profile": self.moderator_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.BEGINNER,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.SELF_LEARNING,
                "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
                "course_type": Course.CourseTypeChoices.KNOWLEDGE,
                "pricing_type": Course.PricingTypeChoices.FREE,
                "duration_hours": 8,
                "lessons_count": 4,
                "status": Course.StatusChoices.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["slug"], "backend-engineering-2")

    def test_partial_update_course(self):
        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {
                "title": "Backend Engineering Pro",
                "tag_ids": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Backend Engineering Pro")
        self.assertEqual(response.data["slug"], "backend-engineering-pro")
        self.assertEqual(response.data["tags"], [])

    def test_partial_update_does_not_allow_slug_override(self):
        self.course.status = Course.StatusChoices.REVIEW
        self.course.save(update_fields=["status"])

        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {
                "title": "Backend Engineering Updated",
                "slug": "teacher-edited-slug",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "backend-engineering")

    def test_partial_update_regenerates_slug_for_draft_when_title_changes(self):
        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {"title": "Backend Engineering Intensive"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "backend-engineering-intensive")

    def test_partial_update_keeps_slug_for_non_draft_when_title_changes(self):
        self.course.status = Course.StatusChoices.REVIEW
        self.course.save(update_fields=["status"])

        response = self.client.patch(
            reverse("courses-detail", args=[self.course.slug]),
            {"title": "Backend Engineering Intensive"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "backend-engineering")

    def test_soft_delete_course(self):
        response = self.client.delete(reverse("courses-detail", args=[self.course.slug]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.course.refresh_from_db()
        self.assertTrue(self.course.is_deleted)
        self.assertEqual(self.course.status, Course.StatusChoices.ARCHIVED)
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())


class CoursePricingRulesTests(APITestCase):
    def setUp(self):
        teacher_user, self.teacher_profile = make_teacher()
        moderator_user = User.objects.create_user(
            email="moderator@example.com",
            password="pass12345",
            role="moderator",
        )
        self.moderator_profile = ModeratorProfile.objects.create(
            user=moderator_user, level="senior"
        )
        self.client.force_authenticate(user=teacher_user)
        self.category = make_category()

    def test_create_free_course_normalizes_price_and_installments(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Free Django Basics",
                "short_description": "Learn the basics",
                "full_description": "Introductory course content.",
                "teacher_profile": self.teacher_profile.pk,
                "moderator_profile": self.moderator_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.BEGINNER,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.SELF_LEARNING,
                "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
                "course_type": Course.CourseTypeChoices.KNOWLEDGE,
                "pricing_type": Course.PricingTypeChoices.FREE,
                "price": "149.99",
                "installment_count": 6,
                "installment_amount": "24.99",
                "duration_hours": 8,
                "lessons_count": 4,
                "status": Course.StatusChoices.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["price"], "0.00")
        self.assertIsNone(response.data["installment_count"])
        self.assertIsNone(response.data["installment_amount"])

    def test_partial_update_full_payment_clears_installment_fields(self):
        installment_course = make_course(
            self.teacher_profile,
            title="Installment Course",
            slug="installment-course",
            short_description="Pay in parts",
            full_description="Installment pricing example.",
            moderator_profile=self.moderator_profile,
            category=self.category,
            level=Course.LevelChoices.INTERMEDIATE,
            mode=Course.ModeChoices.WITH_TEACHER,
            delivery_type=Course.DeliveryTypeChoices.GROUP,
            course_type=Course.CourseTypeChoices.PROFESSION,
            pricing_type=Course.PricingTypeChoices.INSTALLMENT,
            price="300.00",
            installment_count=3,
            installment_amount="100.00",
            duration_hours=18,
            lessons_count=9,
            status=Course.StatusChoices.REVIEW,
        )

        response = self.client.patch(
            reverse("courses-detail", args=[installment_course.slug]),
            {
                "pricing_type": Course.PricingTypeChoices.FULL_PAYMENT,
                "price": "300.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["installment_count"])
        self.assertIsNone(response.data["installment_amount"])

        installment_course.refresh_from_db()
        self.assertIsNone(installment_course.installment_count)
        self.assertIsNone(installment_course.installment_amount)

    def test_installment_pricing_requires_installment_fields(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Broken Installments",
                "short_description": "Missing installment data",
                "full_description": "This should fail.",
                "teacher_profile": self.teacher_profile.pk,
                "moderator_profile": self.moderator_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.BEGINNER,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.WITH_TEACHER,
                "delivery_type": Course.DeliveryTypeChoices.INDIVIDUAL,
                "course_type": Course.CourseTypeChoices.KNOWLEDGE,
                "pricing_type": Course.PricingTypeChoices.INSTALLMENT,
                "price": "120.00",
                "duration_hours": 10,
                "lessons_count": 5,
                "status": Course.StatusChoices.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("installment_count", response.data)
        self.assertIn("installment_amount", response.data)

    def test_full_payment_with_zero_price_rejected(self):
        response = self.client.post(
            reverse("courses-list"),
            {
                "title": "Free But Paid",
                "short_description": "Bad combo",
                "full_description": "Full payment with zero price.",
                "teacher_profile": self.teacher_profile.pk,
                "moderator_profile": self.moderator_profile.pk,
                "category_id": self.category.pk,
                "level": Course.LevelChoices.BEGINNER,
                "language": Course.LanguageChoices.ENGLISH,
                "mode": Course.ModeChoices.SELF_LEARNING,
                "delivery_type": Course.DeliveryTypeChoices.SELF_PACED,
                "course_type": Course.CourseTypeChoices.KNOWLEDGE,
                "pricing_type": Course.PricingTypeChoices.FULL_PAYMENT,
                "price": "0",
                "duration_hours": 5,
                "lessons_count": 2,
                "status": Course.StatusChoices.DRAFT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("price", response.data)
